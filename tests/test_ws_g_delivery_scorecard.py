"""WS-G delivery scorecard + SWE-bench-style mutation probe (DAS-1591, FR-003 / ED-3).

The golden-eval harness extension (`scripts/agent_eval.py`) that scores an autonomous
*delivery* against the six ED-1 completion-contract dimensions and emits the
machine-readable `DeliveryScorecard`. Coverage maps to the ticket's test contract and
the design (`docs/design/ws-g-proof-delivery.md` §1) + ADR-0020 (no false-green):

  * flag-OFF inert — with `ws_g_proof` OFF the scorecard does not score (SC-003);
  * the committed fixture yields `verdict: incomplete` — a fixture NEVER self-certifies;
  * an all-pass constructed delivery is the ONLY green (conjunctive `passed`);
  * a delivery missing ANY one dimension's artifact is not green (that dim → SKIPPED);
  * a present-but-invalid artifact FAILS its dimension → not green;
  * SKIPPED is never a pass (ADR-0020, the load-bearing rule);
  * the mutation probe FAILS a gaming suite (green vs a gutted impl) and PASSES an
    honest suite (red vs the mutant);
  * the degenerate boundary is inherited (an empty submission earns 0.0);
  * `e2e` is excluded from role discovery — the fixture never pollutes the roster.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import agent_eval as ae  # noqa: E402  (import after path manipulation)

FIXTURE = REPO_ROOT / "evals" / "e2e" / "proof-delivery-fixture"

# --------------------------------------------------------------------------- #
# Delivery builders — construct a complete/variant delivery in a tmp dir, exactly
# like test_e2e_sample_pack copies packs into tmp and never mutates the committed tree.
# --------------------------------------------------------------------------- #

_COUNTED_EVENTS = [
    {"run_id": "r1", "to_status": "done", "merged_pr": True, "ci_status": "green", "t7_pass": True},
    {"run_id": "r2", "event_type": "run_end", "merged_pr": True, "ci_status": "passed", "t7_pass": True},
]

_STAGE_BOARD = "\n".join(f"- GATE-{g}: closed" for g in range(1, 7)) + "\n"

_ATTESTATION = {
    "schema": "daslab.wave_attestation.v1",
    "mechanics": {
        "checkpoint_open": True,
        "ledger_written": True,
        "evidence_written": True,
        "checkpoint_close": True,
    },
    "attest_chain": {"prev": "sha256:" + "a" * 64, "self": "sha256:" + "b" * 64},
}

_HONEST_IMPL = (
    "def add(a, b):\n"
    "    return a + b\n"
)
_HONEST_TEST = (
    "import impl\n"
    "def test_add():\n"
    "    assert impl.add(2, 3) == 5\n"
)
# A GAMING suite — green regardless of the implementation (stays green under the mutant).
_GAMING_TEST = (
    "import impl  # noqa: F401\n"
    "def test_always():\n"
    "    assert True\n"
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _complete_delivery(root: Path, *, impl: str = _HONEST_IMPL, test: str = _HONEST_TEST) -> Path:
    """A delivery whose ALL SIX dimensions have a valid committed artifact."""
    fx = root / "fixtures"
    _write(fx / "stage-board.md", _STAGE_BOARD)
    _write(fx / "counted-tickets.json", json.dumps(_COUNTED_EVENTS))
    _write(fx / "wave-attestation.json", json.dumps(_ATTESTATION))
    _write(fx / "diagnostics.json", json.dumps({"score": 100, "max": 100, "clean_tree": True}))
    _write(fx / "golden-eval.json", json.dumps({"accuracy": 0.92, "bar": 0.8}))
    _write(fx / "impl.py", impl)
    _write(fx / "test_impl.py", test)
    return root


def _status_of(card: ae.DeliveryScorecard, dim: str) -> str:
    return next(d.status for d in card.dimensions if d.dimension == dim)


# --------------------------------------------------------------------------- #
# 1. Flag-OFF inert (SC-003)
# --------------------------------------------------------------------------- #

def test_flag_off_is_inert(tmp_path: Path) -> None:
    card = ae.score_delivery(_complete_delivery(tmp_path / "d"), enabled=False)
    assert card.inert is True
    assert card.dimensions == []
    assert card.passed is False
    assert card.verdict == "incomplete"


def test_default_reads_flag_and_is_inert_when_off(tmp_path: Path) -> None:
    # ws_g_proof defaults OFF in config/features.yaml — no explicit override → inert.
    card = ae.score_delivery(_complete_delivery(tmp_path / "d"))
    assert card.inert is True


def test_features_yaml_keeps_ws_g_proof_off() -> None:
    import feature_flags
    assert feature_flags.enabled("ws_g_proof") is False


# --------------------------------------------------------------------------- #
# 2. The committed fixture yields verdict: incomplete (never self-certifies)
# --------------------------------------------------------------------------- #

def test_committed_fixture_is_incomplete() -> None:
    card = ae.score_delivery(FIXTURE, enabled=True)
    assert card.passed is False
    assert card.verdict == "incomplete"
    # D1/D5/D6 measurable+pass; D2/D3/D4 honestly skipped on a labeled fixture.
    assert _status_of(card, "aadl_gates_closed") == "pass"
    assert _status_of(card, "golden_eval") == "pass"
    assert _status_of(card, "anti_gaming_probe") == "pass"
    for dim in ("merged_pr_green_ci", "wave_attestation", "diagnostics_100"):
        assert _status_of(card, dim) == "skipped"


def test_fixture_scorecard_schema_shape() -> None:
    d = ae.score_delivery(FIXTURE, enabled=True).to_dict()
    assert d["schema"] == "daslab.delivery_scorecard.v1"
    assert d["proof"] == "proof-delivery-fixture"
    assert d["passed"] is False
    assert d["verdict"] == "incomplete"
    assert {r["dimension"] for r in d["dimensions"]} == set(ae.ED1_DIMENSIONS)
    # every dimension carries an honest tri-state
    assert all(r["status"] in {"pass", "fail", "skipped"} for r in d["dimensions"])


# --------------------------------------------------------------------------- #
# 3. An all-pass delivery is the ONLY green (conjunctive verdict)
# --------------------------------------------------------------------------- #

def test_all_pass_delivery_is_the_only_green(tmp_path: Path) -> None:
    card = ae.score_delivery(_complete_delivery(tmp_path / "complete"), enabled=True)
    assert [d.status for d in card.dimensions] == ["pass"] * 6
    assert card.passed is True
    assert card.verdict == "complete"


# --------------------------------------------------------------------------- #
# 4. Missing ANY one dimension's artifact → that dimension SKIPPED → not green
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    ("artifact", "dim"),
    [
        ("stage-board.md", "aadl_gates_closed"),
        ("counted-tickets.json", "merged_pr_green_ci"),
        ("wave-attestation.json", "wave_attestation"),
        ("diagnostics.json", "diagnostics_100"),
        ("golden-eval.json", "golden_eval"),
        ("impl.py", "anti_gaming_probe"),
        ("test_impl.py", "anti_gaming_probe"),
    ],
)
def test_missing_one_artifact_skips_that_dimension(tmp_path: Path, artifact: str, dim: str) -> None:
    root = _complete_delivery(tmp_path / "missing")
    (root / "fixtures" / artifact).unlink()
    card = ae.score_delivery(root, enabled=True)
    assert _status_of(card, dim) == "skipped"
    assert card.passed is False  # a skip is never a pass (ADR-0020)
    assert card.verdict == "incomplete"


def test_empty_delivery_all_skipped_not_green(tmp_path: Path) -> None:
    (tmp_path / "empty" / "fixtures").mkdir(parents=True)
    card = ae.score_delivery(tmp_path / "empty", enabled=True)
    # every artifact-backed dimension is skipped; the probe is skipped (no impl/test).
    assert {d.status for d in card.dimensions} == {"skipped"}
    assert card.passed is False


# --------------------------------------------------------------------------- #
# 5. A present-but-INVALID artifact FAILS its dimension → not green
# --------------------------------------------------------------------------- #

def test_open_gate_fails_d1(tmp_path: Path) -> None:
    root = _complete_delivery(tmp_path / "d")
    _write(root / "fixtures" / "stage-board.md", "- GATE-1: closed\n- GATE-4: open\n")
    card = ae.score_delivery(root, enabled=True)
    assert _status_of(card, "aadl_gates_closed") == "fail"
    assert card.passed is False


def test_uncounted_completion_fails_d2(tmp_path: Path) -> None:
    root = _complete_delivery(tmp_path / "d")
    bad = [{"run_id": "r1", "to_status": "done", "merged_pr": True, "ci_status": "red", "t7_pass": True}]
    _write(root / "fixtures" / "counted-tickets.json", json.dumps(bad))
    card = ae.score_delivery(root, enabled=True)
    assert _status_of(card, "merged_pr_green_ci") == "fail"
    assert card.passed is False


def test_unfired_mechanic_fails_d3(tmp_path: Path) -> None:
    root = _complete_delivery(tmp_path / "d")
    broken = json.loads(json.dumps(_ATTESTATION))
    broken["mechanics"]["ledger_written"] = False
    _write(root / "fixtures" / "wave-attestation.json", json.dumps(broken))
    card = ae.score_delivery(root, enabled=True)
    assert _status_of(card, "wave_attestation") == "fail"


def test_malformed_chain_fails_d3(tmp_path: Path) -> None:
    root = _complete_delivery(tmp_path / "d")
    broken = json.loads(json.dumps(_ATTESTATION))
    broken["attest_chain"] = {"prev": "not-a-digest", "self": "sha256:" + "b" * 64}
    _write(root / "fixtures" / "wave-attestation.json", json.dumps(broken))
    card = ae.score_delivery(root, enabled=True)
    assert _status_of(card, "wave_attestation") == "fail"


def test_diagnostics_below_100_fails_d4(tmp_path: Path) -> None:
    root = _complete_delivery(tmp_path / "d")
    _write(root / "fixtures" / "diagnostics.json", json.dumps({"score": 99, "max": 100, "clean_tree": True}))
    card = ae.score_delivery(root, enabled=True)
    assert _status_of(card, "diagnostics_100") == "fail"


def test_unclean_tree_fails_d4(tmp_path: Path) -> None:
    root = _complete_delivery(tmp_path / "d")
    _write(root / "fixtures" / "diagnostics.json", json.dumps({"score": 100, "max": 100, "clean_tree": False}))
    card = ae.score_delivery(root, enabled=True)
    assert _status_of(card, "diagnostics_100") == "fail"


def test_golden_below_bar_fails_d5(tmp_path: Path) -> None:
    root = _complete_delivery(tmp_path / "d")
    _write(root / "fixtures" / "golden-eval.json", json.dumps({"accuracy": 0.5, "bar": 0.8}))
    card = ae.score_delivery(root, enabled=True)
    assert _status_of(card, "golden_eval") == "fail"


# --------------------------------------------------------------------------- #
# 6. The SWE-bench-style mutation probe (D6, design §1.3)
# --------------------------------------------------------------------------- #

def test_mutation_probe_passes_honest_suite(tmp_path: Path) -> None:
    root = _complete_delivery(tmp_path / "d", impl=_HONEST_IMPL, test=_HONEST_TEST)
    result = ae.mutation_probe(root)
    assert result.status == "pass"


def test_mutation_probe_fails_gaming_suite(tmp_path: Path) -> None:
    # An `assert True` suite is green against BOTH the real impl and the gutted mutant.
    root = _complete_delivery(tmp_path / "d", impl=_HONEST_IMPL, test=_GAMING_TEST)
    result = ae.mutation_probe(root)
    assert result.status == "fail"
    assert "green" in result.detail.lower()


def test_gaming_suite_denies_delivery_green(tmp_path: Path) -> None:
    root = _complete_delivery(tmp_path / "d", test=_GAMING_TEST)
    card = ae.score_delivery(root, enabled=True)
    assert _status_of(card, "anti_gaming_probe") == "fail"
    assert card.passed is False  # a whole complete delivery is denied green by a gaming suite


def test_mutate_source_neutralizes_bodies() -> None:
    mutated = ae._mutate_source("def f(x):\n    return x + 1\n")
    ns: dict = {}
    exec(compile(mutated, "<mut>", "exec"), ns)  # noqa: S102 - trusted, test-local
    assert ns["f"](10) is None


def test_delivery_gaming_findings_flags_gaming_and_clean_honest(tmp_path: Path) -> None:
    gaming = _complete_delivery(tmp_path / "g", test=_GAMING_TEST)
    honest = _complete_delivery(tmp_path / "h", test=_HONEST_TEST)
    assert ae.delivery_gaming_findings(gaming, enabled=True)  # non-empty → flagged
    assert ae.delivery_gaming_findings(honest, enabled=True) == []


# --------------------------------------------------------------------------- #
# 7. Degenerate boundary inherited + fixture verify() reuse
# --------------------------------------------------------------------------- #

def test_degenerate_submission_earns_zero_on_fixture() -> None:
    # The fixture's verify.py reuses the verify(submission, fixtures)->float contract;
    # an empty submission must earn 0.0 (the inherited Goodhart defence).
    assert ae.degenerate_credit(FIXTURE) == 0.0


def test_honest_claim_scores_matching_pass_dimensions() -> None:
    module = ae.load_verifier(FIXTURE)
    submission = json.loads((FIXTURE / "submissions" / "attempt-1.json").read_text())
    credit = ae.score_submission(module, submission, FIXTURE)
    # 3 of 6 dimensions genuinely pass (D1/D5/D6); the honest claim earns exactly those.
    assert credit == pytest.approx(3 / 6)


def test_forged_all_pass_claim_cannot_reach_one() -> None:
    module = ae.load_verifier(FIXTURE)
    forged = {"dimensions": dict.fromkeys(ae.ED1_DIMENSIONS, "pass")}
    credit = ae.score_submission(module, forged, FIXTURE)
    # the three genuinely-skipped dimensions earn no credit no matter the claim.
    assert credit == pytest.approx(3 / 6)
    assert credit < 1.0


# --------------------------------------------------------------------------- #
# 8. Discovery isolation + flag-off byte-identical guard
# --------------------------------------------------------------------------- #

def test_e2e_excluded_from_role_discovery() -> None:
    assert "e2e" in ae._NON_ROLE_ENTRIES
    assert "e2e" not in ae.discover_roles()


def test_delivery_fixture_does_not_leak_into_gaming_gate() -> None:
    # Adding evals/e2e/proof-delivery-fixture/verify.py must NOT make the role-level
    # anti-gaming gate see a new task (e2e is excluded) — no regression.
    assert ae.gaming_findings() == []


# --------------------------------------------------------------------------- #
# 9. CLI
# --------------------------------------------------------------------------- #

def test_cli_delivery_inert_when_flag_off(capsys: pytest.CaptureFixture[str]) -> None:
    rc = ae.main(["--delivery", str(FIXTURE)])
    assert rc == 0
    assert "inert" in capsys.readouterr().out.lower()


def test_run_delivery_enforce_fails_incomplete(monkeypatch: pytest.MonkeyPatch) -> None:
    import argparse
    monkeypatch.setattr(
        ae, "score_delivery",
        lambda _d: ae.DeliveryScorecard(
            proof="x",
            dimensions=[ae.DimensionResult(d, "skipped") for d in ae.ED1_DIMENSIONS],
        ),
    )
    ns = argparse.Namespace(delivery=Path("x"), delivery_enforce=True)
    assert ae._run_delivery(ns) == 1


def test_run_delivery_enforce_passes_complete(monkeypatch: pytest.MonkeyPatch) -> None:
    import argparse
    monkeypatch.setattr(
        ae, "score_delivery",
        lambda _d: ae.DeliveryScorecard(
            proof="x",
            dimensions=[ae.DimensionResult(d, "pass") for d in ae.ED1_DIMENSIONS],
        ),
    )
    ns = argparse.Namespace(delivery=Path("x"), delivery_enforce=True)
    assert ae._run_delivery(ns) == 0


# clean up any stray pycache the fixture verify import may leave (parity w/ other tests)
def teardown_module() -> None:  # noqa: D401
    for pc in (FIXTURE,).__iter__():
        cache = pc / "__pycache__"
        if cache.is_dir():
            shutil.rmtree(cache, ignore_errors=True)
