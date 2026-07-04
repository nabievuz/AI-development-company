"""test_org_schema.py — Org Schema SSOT + generate-and-diff drift gate (E-004, R-12 / ADR-009).

Locks in the Prisma-pattern guarantees:
  - gen_org.render is deterministic and the committed _org_generated.py is in sync,
  - the generated NEVER_AUTO_APPROVE equals the schema + config never_auto_approve,
  - check_org_drift fails (exit 1) on a hand-edited generated module or a schema that
    diverges from config/risk_taxonomy.yaml, and passes (exit 0) on the real tree,
  - the safety validators consume the generated constant (no drift from the SSOT).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

yaml = pytest.importorskip("yaml")

import check_never_auto_approve  # noqa: E402
import check_org_drift  # noqa: E402
import gen_org  # noqa: E402

EXPECTED_NEVER = (
    "new_goal", "security_sensitive", "schema_migration", "gate5_deployment",
    "governance_or_policy", "permission_change", "secret_change",
)


def _schema() -> dict:
    return gen_org.load_schema(gen_org.SCHEMA_PATH)


# ---- generator: deterministic + committed file in sync ----------------------

def test_render_is_deterministic():
    schema = _schema()
    assert gen_org.render(schema) == gen_org.render(schema)


def test_committed_generated_matches_schema():
    """The committed scripts/_org_generated.py must equal a fresh render (no drift)."""
    committed = gen_org.GENERATED_PATH.read_text(encoding="utf-8")
    assert committed == gen_org.render(_schema())


def test_generated_module_banner_is_do_not_edit():
    committed = gen_org.GENERATED_PATH.read_text(encoding="utf-8")
    assert "DO NOT EDIT" in committed
    assert "# ruff: noqa" in committed


def test_generated_never_auto_approve_matches_schema_and_config():
    import _org_generated

    schema_never = set(_schema().get("never_auto_approve", []))
    assert set(_org_generated.NEVER_AUTO_APPROVE) == set(EXPECTED_NEVER) == schema_never

    rt = yaml.safe_load((ROOT / "config" / "risk_taxonomy.yaml").read_text()) or {}
    assert set(rt.get("never_auto_approve", [])) == schema_never


def test_gate_owners_are_sorted_and_complete():
    import _org_generated

    assert set(_org_generated.GATE_OWNERS) == set(_org_generated.GATES)
    for owners in _org_generated.GATE_OWNERS.values():
        assert list(owners) == sorted(owners)
        assert owners  # every gate has at least one owner


# ---- drift gate: passes clean, fails on tamper ------------------------------

def test_drift_gate_passes_on_real_tree(capsys):
    assert check_org_drift.main([]) == 0
    assert "in sync" in capsys.readouterr().out


def test_drift_gate_fails_on_hand_edited_generated(tmp_path):
    tampered = tmp_path / "_org_generated.py"
    real = gen_org.GENERATED_PATH.read_text(encoding="utf-8")
    tampered.write_text(real + "\nSNEAKY = 'edit'\n", encoding="utf-8")
    assert check_org_drift.main(["--generated", str(tampered)]) == 1


def test_drift_gate_fails_on_missing_generated(tmp_path):
    missing = tmp_path / "does_not_exist.py"
    assert check_org_drift.main(["--generated", str(missing)]) == 1


def test_drift_gate_fails_only_on_config_divergence(tmp_path, capsys):
    """Isolates the schema-vs-config CONSISTENCY check. Floor intact (completeness passes),
    generated regenerated (no drift), real config carries all 7 matchers — so ONLY the
    never_auto_approve name-set divergence trips. Fails iff the config-equality check is removed
    (the old test dropped a FLOOR category, so the immutability check fired instead and the
    config check went untested)."""
    schema = _schema()
    schema["never_auto_approve"] = list(EXPECTED_NEVER) + ["extra_non_floor_category"]
    bad_schema = tmp_path / "schema.daslab.yaml"
    bad_schema.write_text(yaml.safe_dump(schema), encoding="utf-8")
    bad_gen = tmp_path / "_org_generated.py"
    bad_gen.write_text(gen_org.render(schema), encoding="utf-8")
    # Default --risk-taxonomy = the real config/risk_taxonomy.yaml (7 names + matchers),
    # so completeness + matcher checks pass and only the name-set divergence remains.
    rc = check_org_drift.main(["--schema", str(bad_schema), "--generated", str(bad_gen)])
    assert rc == 1
    assert "differs from the Org Schema SSOT" in capsys.readouterr().err


def test_drift_gate_missing_schema_is_usage_error(tmp_path):
    assert check_org_drift.main(["--schema", str(tmp_path / "nope.yaml")]) == 2


def test_drift_gate_fails_when_schema_drops_an_immutable_category(tmp_path, capsys):
    """Completeness, not just consistency: dropping a QONUN-5 category from the schema
    must fail EVEN IF schema == config == generated stay mutually consistent."""
    schema = _schema()
    schema["never_auto_approve"] = [c for c in schema["never_auto_approve"] if c != "secret_change"]
    bad_schema = tmp_path / "schema.daslab.yaml"
    bad_schema.write_text(yaml.safe_dump(schema), encoding="utf-8")
    bad_gen = tmp_path / "_org_generated.py"
    bad_gen.write_text(gen_org.render(schema), encoding="utf-8")
    bad_rt = tmp_path / "risk_taxonomy.yaml"
    bad_rt.write_text(yaml.safe_dump({"never_auto_approve": schema["never_auto_approve"]}), encoding="utf-8")
    rc = check_org_drift.main([
        "--schema", str(bad_schema),
        "--generated", str(bad_gen),
        "--risk-taxonomy", str(bad_rt),
    ])
    assert rc == 1
    assert "secret_change" in capsys.readouterr().err


def test_qonun5_floor_constant_is_the_canonical_seven():
    assert frozenset(EXPECTED_NEVER) == check_org_drift.QONUN5_IMMUTABLE


# ---- validators consume the generated SSOT ----------------------------------

def test_never_auto_approve_validator_uses_generated_constant():
    assert check_never_auto_approve._GENERATED_NEVER is not None
    assert set(check_never_auto_approve._GENERATED_NEVER) == set(EXPECTED_NEVER)


def test_adaptive_taxonomy_immutable_set_derives_from_generated():
    import adaptive_taxonomy

    expected = frozenset(EXPECTED_NEVER)
    assert expected == adaptive_taxonomy.IMMUTABLE_NEVER_AUTO


# ---- fail-closed hardening (review findings) --------------------------------

def _config_with(tmp_path, *, names, matchers):
    p = tmp_path / "risk_taxonomy.yaml"
    p.write_text(yaml.safe_dump({"never_auto_approve": list(names), "matchers": matchers}), encoding="utf-8")
    return p


def test_drift_gate_fails_closed_on_absent_risk_taxonomy(tmp_path, capsys):
    """A MISSING config/risk_taxonomy.yaml must fail the gate, not silently skip the
    config-consistency check and print a false 'consistent' assurance (finding #1)."""
    rc = check_org_drift.main(["--risk-taxonomy", str(tmp_path / "gone.yaml")])
    assert rc == 1
    assert "missing" in capsys.readouterr().err


def test_drift_gate_fails_when_an_immutable_matcher_is_dropped(tmp_path, capsys):
    """A QONUN-5 category present in never_auto_approve but with NO (or empty) matcher
    protects zero tickets — the gate must catch matcher incompleteness, not just names
    (finding #3). Real schema + generated kept clean; only the matcher map is gutted."""
    rt = _config_with(tmp_path, names=EXPECTED_NEVER, matchers={
        c: ({"labels": [c]} if c != "secret_change" else {}) for c in EXPECTED_NEVER
    })
    rc = check_org_drift.main(["--risk-taxonomy", str(rt)])
    assert rc == 1
    assert "secret_change" in capsys.readouterr().err


def test_drift_gate_fails_when_matchers_map_is_emptied(tmp_path):
    """Gutting the entire matchers map (every selector stripped) must fail closed."""
    rt = _config_with(tmp_path, names=EXPECTED_NEVER, matchers={})
    assert check_org_drift.main(["--risk-taxonomy", str(rt)]) == 1


def test_drift_gate_fails_on_non_mapping_risk_taxonomy(tmp_path):
    """A risk_taxonomy that parses to a top-level list/scalar (not a mapping) must fail
    closed, not silently skip the config checks."""
    rt = tmp_path / "risk_taxonomy.yaml"
    rt.write_text("- new_goal\n- secret_change\n", encoding="utf-8")
    assert check_org_drift.main(["--risk-taxonomy", str(rt)]) == 1


@pytest.mark.parametrize("inert", [
    {"paths": [""]},          # empty-string glob — matches nothing
    {"paths": ["   "]},       # whitespace-only glob
    {"paths": [None]},        # null list element (would crash the unhardened matcher)
    {"paths": True},          # bool, not a list
    {"labels": [""]},
    {"labels": ["  "]},
    {"labels": {"a": 1}},     # dict-valued selector — iterates keys, binds nothing
    {"ticket_type": [""]},
    {"stage": [""]},
    {},                        # no selectors at all
])
def test_drift_gate_rejects_inert_floor_matcher(tmp_path, inert):
    """A floor matcher that is PRESENT but binds NO ticket must fail the gate — truthiness
    is not usability. The gate's notion of 'binds' is nap._clean_tokens, identical to the
    runtime matcher's, so every truthy-but-inert shape the second-pass review found is caught."""
    matchers = {c: {"labels": [c]} for c in EXPECTED_NEVER}
    matchers["secret_change"] = inert
    rt = _config_with(tmp_path, names=EXPECTED_NEVER, matchers=matchers)
    assert check_org_drift.main(["--risk-taxonomy", str(rt)]) == 1


def test_drift_gate_accepts_scalar_selector_that_binds(tmp_path):
    """A SCALAR (non-list) selector that yields a real token binds at runtime (the matcher
    side is now coerced like the ticket side), so the gate accepts it — gate-binds == runtime-binds."""
    matchers = {c: {"labels": [c]} for c in EXPECTED_NEVER}
    matchers["secret_change"] = {"paths": "**/.env*"}  # scalar, not a list
    rt = _config_with(tmp_path, names=EXPECTED_NEVER, matchers=matchers)
    assert check_org_drift.main(["--risk-taxonomy", str(rt)]) == 0


@pytest.mark.parametrize("matcher", [
    {"paths": [None]}, {"paths": True}, {"paths": [True, None]},
    {"ticket_type": True}, {"labels": {"a": 1}}, {"stage": None},
])
def test_matches_category_never_crashes_on_malformed_matcher(matcher):
    """A malformed matcher element (None / bool / dict) binds nothing rather than raising
    AttributeError/TypeError — protecting check_never_auto_approve + intent_preview + approval_digest."""
    fm = {"approval": "auto", "paths": ["config/prod/.env.production"], "labels": ["x"]}
    assert check_never_auto_approve.matches_category(fm, matcher) is False


def test_matches_category_binds_scalar_path_and_label_selectors():
    """A scalar paths/labels selector binds the same as its one-item list form."""
    assert check_never_auto_approve.matches_category(
        {"paths": ["config/prod/.env.production"]}, {"paths": "**/.env*"}) is True
    assert check_never_auto_approve.matches_category(
        {"labels": ["security"]}, {"labels": "security"}) is True


@pytest.mark.parametrize("fm,matcher", [
    ({"stage": "GATE-5"}, {"stage": ["gate-5"]}),          # mis-cased matcher token
    ({"stage": "gate-5"}, {"stage": ["GATE-5"]}),          # mis-cased ticket value
    ({"labels": ["Security"]}, {"labels": ["security"]}),  # label casing
    ({"ticket_type": "Goal"}, {"ticket_type": ["goal"]}),
])
def test_matches_category_is_case_insensitive_for_non_path_selectors(fm, matcher):
    """A never-auto-approve gate errs toward catching MORE: a casing mismatch in a
    type/stage/label selector still binds, so a QONUN-5 ticket can't slip through on case."""
    assert check_never_auto_approve.matches_category(fm, matcher) is True


def test_null_matcher_does_not_crash_validator(tmp_path):
    """A null-bodied matcher (`secret_change:` with no mapping -> None) must not raise an
    AttributeError mid-scan; matches_category treats a non-dict matcher as 'matches nothing'
    (finding #4). The board ticket is benign, so the run is clean (exit 0), not a traceback."""
    assert check_never_auto_approve.matches_category({"approval": "auto"}, None) is False
    cfg = tmp_path / "risk_taxonomy.yaml"
    cfg.write_text("never_auto_approve: [secret_change]\nmatchers:\n  secret_change:\n", encoding="utf-8")
    board = tmp_path / "board"
    board.mkdir()
    (board / "DAS-benign.md").write_text("---\nid: DAS-benign\napproval: manual:cxo\n---\n", encoding="utf-8")
    assert check_never_auto_approve.main(["--board", str(board), "--config", str(cfg)]) == 0


def test_floor_union_protects_dropped_generated_category(tmp_path, monkeypatch):
    """If the generated constant were SHORTENED to a strict subset of the floor, the
    hard-coded floor UNION must still make the validator flag a dropped category. Fails iff
    `| set(_QONUN5_FLOOR)` is removed from check_never_auto_approve.main (finding #6)."""
    monkeypatch.setattr(check_never_auto_approve, "_GENERATED_NEVER",
                        ("new_goal", "security_sensitive", "permission_change"))  # secret_change dropped
    board = tmp_path / "board"
    board.mkdir()
    (board / "DAS-secret.md").write_text(
        "---\nid: DAS-secret\napproval: auto\npaths: ['config/prod/.env.production']\n---\n",
        encoding="utf-8")
    rc = check_never_auto_approve.main([
        "--board", str(board), "--config", str(ROOT / "config" / "risk_taxonomy.yaml")])
    assert rc == 1  # secret_change still enforced via the floor union, not the generated set


def test_adaptive_immutable_floor_survives_shortened_generated():
    """adaptive_taxonomy.IMMUTABLE_NEVER_AUTO must stay >= the 7-category floor even if the
    generated module is shortened to a strict subset. Reloads the module with a patched
    _org_generated; fails iff the `_QONUN5_FLOOR |` union is dropped (finding #6)."""
    import importlib

    import _org_generated
    import adaptive_taxonomy
    real = _org_generated.NEVER_AUTO_APPROVE
    try:
        _org_generated.NEVER_AUTO_APPROVE = ("new_goal", "security_sensitive", "permission_change")
        reloaded = importlib.reload(adaptive_taxonomy)
        assert frozenset(EXPECTED_NEVER) <= reloaded.IMMUTABLE_NEVER_AUTO
    finally:
        _org_generated.NEVER_AUTO_APPROVE = real
        importlib.reload(adaptive_taxonomy)
