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

import agent_eval as ae

FIXTURE = REPO_ROOT / "evals" / "e2e" / "proof-delivery-fixture"


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

_GAMING_TEST = (
    "import impl  # noqa: F401\n"
    "def test_always():\n"
    "    assert True\n"
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _complete_delivery(root: Path, *, impl: str = _HONEST_IMPL, test: str = _HONEST_TEST) -> Path:
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


def test_flag_off_is_inert(tmp_path: Path) -> None:
    card = ae.score_delivery(_complete_delivery(tmp_path / "d"), enabled=False)
    assert card.inert is True
    assert card.dimensions == []
    assert card.passed is False
    assert card.verdict == "incomplete"


def test_score_delivery_is_flag_gated(tmp_path: Path) -> None:


    d = _complete_delivery(tmp_path / "d")
    assert ae.score_delivery(d, enabled=False).inert is True
    assert ae.score_delivery(d, enabled=True).inert is False


def test_features_yaml_ws_g_proof_on_after_activation() -> None:

    import feature_flags
    assert feature_flags.enabled("ws_g_proof") is True


def test_committed_fixture_is_incomplete() -> None:
    card = ae.score_delivery(FIXTURE, enabled=True)
    assert card.passed is False
    assert card.verdict == "incomplete"

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

    assert all(r["status"] in {"pass", "fail", "skipped"} for r in d["dimensions"])


def test_all_pass_delivery_is_the_only_green(tmp_path: Path) -> None:
    card = ae.score_delivery(_complete_delivery(tmp_path / "complete"), enabled=True)
    assert [d.status for d in card.dimensions] == ["pass"] * 6
    assert card.passed is True
    assert card.verdict == "complete"


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
    assert card.passed is False
    assert card.verdict == "incomplete"


def test_empty_delivery_all_skipped_not_green(tmp_path: Path) -> None:
    (tmp_path / "empty" / "fixtures").mkdir(parents=True)
    card = ae.score_delivery(tmp_path / "empty", enabled=True)

    assert {d.status for d in card.dimensions} == {"skipped"}
    assert card.passed is False


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


def test_mutation_probe_passes_honest_suite(tmp_path: Path) -> None:
    root = _complete_delivery(tmp_path / "d", impl=_HONEST_IMPL, test=_HONEST_TEST)
    result = ae.mutation_probe(root)
    assert result.status == "pass"


def test_mutation_probe_fails_gaming_suite(tmp_path: Path) -> None:

    root = _complete_delivery(tmp_path / "d", impl=_HONEST_IMPL, test=_GAMING_TEST)
    result = ae.mutation_probe(root)
    assert result.status == "fail"
    assert "green" in result.detail.lower()


def test_gaming_suite_denies_delivery_green(tmp_path: Path) -> None:
    root = _complete_delivery(tmp_path / "d", test=_GAMING_TEST)
    card = ae.score_delivery(root, enabled=True)
    assert _status_of(card, "anti_gaming_probe") == "fail"
    assert card.passed is False


def test_mutate_source_neutralizes_bodies() -> None:
    mutated = ae._mutate_source("def f(x):\n    return x + 1\n")
    ns: dict = {}
    exec(compile(mutated, "<mut>", "exec"), ns)
    assert ns["f"](10) is None


def test_delivery_gaming_findings_flags_gaming_and_clean_honest(tmp_path: Path) -> None:
    gaming = _complete_delivery(tmp_path / "g", test=_GAMING_TEST)
    honest = _complete_delivery(tmp_path / "h", test=_HONEST_TEST)
    assert ae.delivery_gaming_findings(gaming, enabled=True)
    assert ae.delivery_gaming_findings(honest, enabled=True) == []


def test_degenerate_submission_earns_zero_on_fixture() -> None:


    assert ae.degenerate_credit(FIXTURE) == 0.0


def test_honest_claim_scores_matching_pass_dimensions() -> None:
    module = ae.load_verifier(FIXTURE)
    submission = json.loads((FIXTURE / "submissions" / "attempt-1.json").read_text())
    credit = ae.score_submission(module, submission, FIXTURE)

    assert credit == pytest.approx(3 / 6)


def test_forged_all_pass_claim_cannot_reach_one() -> None:
    module = ae.load_verifier(FIXTURE)
    forged = {"dimensions": dict.fromkeys(ae.ED1_DIMENSIONS, "pass")}
    credit = ae.score_submission(module, forged, FIXTURE)

    assert credit == pytest.approx(3 / 6)
    assert credit < 1.0


def test_e2e_excluded_from_role_discovery() -> None:
    assert "e2e" in ae._NON_ROLE_ENTRIES
    assert "e2e" not in ae.discover_roles()


def test_delivery_fixture_does_not_leak_into_gaming_gate() -> None:


    assert ae.gaming_findings() == []


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


def teardown_module() -> None:
    for pc in (FIXTURE,).__iter__():
        cache = pc / "__pycache__"
        if cache.is_dir():
            shutil.rmtree(cache, ignore_errors=True)
