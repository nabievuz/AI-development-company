from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS = _REPO_ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import agent_eval as ae
import check_evidence_gate as ceg
import wave_runner as wr

_ROUTING = _REPO_ROOT / "board" / "ROUTING.md"
_GUARDRAILS = _REPO_ROOT / "governance" / "guardrails"

_WAVE_TS = "2026-07-24T12:00:00Z"
_END_TS = "2026-07-24T12:10:00Z"
_CREATED_AT = "2026-07-24T12:41:00Z"

_STAGE_BOARD_CLOSED = "\n".join(f"Gate-{g}: closed" for g in range(1, 7)) + "\n"
_HONEST_IMPL = "def add(a, b):\n    return a + b\n"
_HONEST_TEST = "from impl import add\n\ndef test_add():\n    assert add(2, 3) == 5\n"
_GAMING_TEST = "def test_always():\n    assert True\n"


_WEAK_TENSION_TEST = (
    "from impl import add\n\ndef test_add_returns_something():\n"
    "    assert add(2, 3) is not None\n"
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_ticket(board: Path, ticket_id: str, assignee: str) -> None:
    board.mkdir(parents=True, exist_ok=True)
    (board / f"{ticket_id}-synthetic.md").write_text(
        "---\n"
        f"id: {ticket_id}\n"
        "title: Synthetic fixture\n"
        "status: in_progress\n"
        f"assignee: {assignee}\n"
        "author: cto\ndept: engineering\npriority: p1\n"
        "---\n\n## Description\nSynthetic.\n",
        encoding="utf-8",
    )


def _drive_real_wave(tmp: Path, run_id: str) -> wr.WaveAttestation:
    board = tmp / "board" / "tickets"
    _write_ticket(board, "DAS-9201", "backend-eng-1")
    _write_ticket(board, "DAS-9202", "backend-eng-2")
    common = {
        "outcome": "success",
        "merged_pr": True,
        "ci_status": "green",
        "t7_pass": True,
        "t7_score": 0.95,
        "start": _WAVE_TS,
        "end": _END_TS,
        "final_status": "done",
        "output": "done; tests green.",
    }
    plan = wr.WavePlan(
        run_id=run_id,
        wave=1,
        goal="ws-g-proof-delivery-acceptance-fixture",
        engine_version="1.0.0",
        tickets=[
            wr.TicketPlan("DAS-9201", "backend-eng-1", "opus"),
            wr.TicketPlan("DAS-9202", "backend-eng-2", "sonnet"),
        ],
    )
    results = wr.WaveResults(
        tickets=[
            wr.TicketResult(ticket_id="DAS-9201", **common),
            wr.TicketResult(ticket_id="DAS-9202", **common),
        ]
    )
    att = wr.run_wave(
        plan,
        wr.replay_executor(results.tickets),
        created_at=_WAVE_TS,
        store_path=tmp / "events.jsonl",
        runs_dir=tmp / "runs",
        attest_dir=tmp / "attest",
        ledger_path=tmp / "board" / "wave-ledger.jsonl",
        evidence_dir=tmp / "evidence",
        tickets_dir=board,
        board_dir=board,
        routing_path=_ROUTING,
        guardrails_dir=_GUARDRAILS,
    )
    assert att is not None
    return att


def _complete_delivery(root: Path, *, impl: str = _HONEST_IMPL, test: str = _HONEST_TEST) -> Path:
    fx = root / "fixtures"
    _write(fx / "stage-board.md", _STAGE_BOARD_CLOSED)
    _write(
        fx / "counted-tickets.json",
        json.dumps(
            [
                {"run_id": "r1", "to_status": "done", "merged_pr": True, "ci_status": "green", "t7_pass": True},
                {"run_id": "r2", "event_type": "run_end", "merged_pr": True, "ci_status": "passed", "t7_pass": True},
            ]
        ),
    )
    _write(
        fx / "wave-attestation.json",
        json.dumps(
            {
                "schema": "daslab.wave_attestation.v1",
                "mechanics": {
                    "checkpoint_open": True,
                    "ledger_written": True,
                    "evidence_written": True,
                    "checkpoint_close": True,
                },
                "attest_chain": {"prev": "sha256:" + "a" * 64, "self": "sha256:" + "b" * 64},
            }
        ),
    )
    _write(fx / "diagnostics.json", json.dumps({"score": 100, "max": 100, "clean_tree": True}))
    _write(fx / "golden-eval.json", json.dumps({"accuracy": 0.92, "bar": 0.8}))
    _write(fx / "impl.py", impl)
    _write(fx / "test_impl.py", test)
    return root


def _status_of(card: ae.DeliveryScorecard, dim: str) -> str:
    return next(d.status for d in card.dimensions if d.dimension == dim)


def _flag_path(tmp: Path, *, on: bool) -> Path:
    path = tmp / "features.yaml"
    path.write_text(f"ws_g_proof: {'true' if on else 'false'}\n", encoding="utf-8")
    return path


def _run_gate(tmp: Path, scorecard: Path | None, flags: Path, delivery_dir: Path | None = None) -> int:
    argv = [
        "--attest-dir", str(tmp / "attest"),
        "--evidence-dir", str(tmp / "evidence"),
        "--created-at", _CREATED_AT,
        "--features", str(flags),
    ]
    if scorecard is not None:
        argv += ["--scorecard", str(scorecard)]
    if delivery_dir is not None:
        argv += ["--delivery-dir", str(delivery_dir)]
    return ceg.main(argv)


def test_sc001_all_pass_is_the_only_green(tmp_path: Path) -> None:
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
    ],
)
def test_sc001_missing_any_single_dimension_denies_green(
    tmp_path: Path, artifact: str, dim: str
) -> None:
    root = _complete_delivery(tmp_path / "missing")
    (root / "fixtures" / artifact).unlink()
    card = ae.score_delivery(root, enabled=True)
    assert _status_of(card, dim) == "skipped"
    assert card.passed is False
    assert card.verdict == "incomplete"


    passing = [d for d in card.dimensions if d.status == "pass"]
    assert len(passing) == 5


def test_sc001_skip_never_rounds_up_regardless_of_how_many_pass() -> None:
    all_pass = dict.fromkeys(ceg.SIX_DIMENSIONS, "pass")
    assert ceg.verdict_of(all_pass) == "complete"
    for dim in ceg.SIX_DIMENSIONS:
        one_skip = dict(all_pass)
        one_skip[dim] = "skipped"
        assert ceg.verdict_of(one_skip) == "incomplete"


def test_sc004_forge_negative_bound_gate3_handoff(tmp_path: Path) -> None:
    att = _drive_real_wave(tmp_path, "01JPROOFFORGE000000000001")
    scorecard_payload = {
        "schema": ceg.SCORECARD_SCHEMA,
        "proof": "ws-g-proof-delivery-acceptance",
        "run_id": att.run_id,
        "passed": True,
        "dimensions": [{"dimension": d, "status": "pass", "evidence_ref": "forged"} for d in ceg.SIX_DIMENSIONS],
    }
    scorecard_path = tmp_path / "scorecard.json"
    scorecard_path.write_text(json.dumps(scorecard_payload), encoding="utf-8")

    rc = _run_gate(tmp_path, scorecard_path, _flag_path(tmp_path, on=True))
    assert rc != 0, "a forged all-pass scorecard with no real D1/D4/D5/D6 artifacts MUST be rejected"

    receipt = json.loads((tmp_path / "attest" / f"{att.run_id}.delivery.json").read_text())
    assert receipt["verdict"] == "incomplete"

    assert receipt["dimensions"]["merged_pr_green_ci"] == "pass"
    assert receipt["dimensions"]["wave_attestation"] == "pass"

    for dim in ("aadl_gates_closed", "diagnostics_100", "golden_eval", "anti_gaming_probe"):
        assert receipt["dimensions"][dim] == "skipped", (dim, receipt["dimensions"][dim])


def test_sc004_forged_scorecard_disagreeing_with_real_artifacts_rejected(tmp_path: Path) -> None:
    root = _complete_delivery(tmp_path)
    _write(root / "fixtures" / "stage-board.md", "Gate-1: closed\nGate-4: open\n")
    _write(root / "fixtures" / "diagnostics.json", json.dumps({"score": 87, "max": 100, "clean_tree": True}))
    att = _drive_real_wave(tmp_path, "01JPROOFFORGE000000000002")

    scorecard_payload = {
        "schema": ceg.SCORECARD_SCHEMA,
        "proof": "ws-g-proof-delivery-acceptance",
        "run_id": att.run_id,
        "passed": True,
        "dimensions": [{"dimension": d, "status": "pass", "evidence_ref": "forged"} for d in ceg.SIX_DIMENSIONS],
    }
    scorecard_path = tmp_path / "scorecard.json"
    scorecard_path.write_text(json.dumps(scorecard_payload), encoding="utf-8")

    rc = _run_gate(tmp_path, scorecard_path, _flag_path(tmp_path, on=True))
    assert rc != 0

    receipt = json.loads((tmp_path / "attest" / f"{att.run_id}.delivery.json").read_text())
    assert receipt["verdict"] == "incomplete"
    assert receipt["dimensions"]["aadl_gates_closed"] == "fail"
    assert receipt["dimensions"]["diagnostics_100"] == "fail"


def test_sc003_flag_off_scorecard_and_gate_are_both_inert(tmp_path: Path, capsys) -> None:
    complete = _complete_delivery(tmp_path / "d")


    card = ae.score_delivery(complete, enabled=False)
    assert card.inert is True
    assert card.dimensions == []
    assert card.passed is False


    att = _drive_real_wave(tmp_path, "01JPROOFFLAGOFF00000001")
    scorecard_payload = {
        "schema": ceg.SCORECARD_SCHEMA,
        "proof": "ws-g-proof-delivery-acceptance",
        "run_id": att.run_id,
        "dimensions": [{"dimension": d, "status": "pass"} for d in ceg.SIX_DIMENSIONS],
    }
    scorecard_path = tmp_path / "scorecard.json"
    scorecard_path.write_text(json.dumps(scorecard_payload), encoding="utf-8")

    rc = _run_gate(tmp_path, scorecard_path, _flag_path(tmp_path, on=False), delivery_dir=complete)
    assert rc == 0
    assert "inert" in capsys.readouterr().out
    assert not (tmp_path / "attest" / f"{att.run_id}.delivery.json").exists()


def test_sc003_features_yaml_ws_g_proof_on_after_activation() -> None:


    import feature_flags

    assert feature_flags.enabled("ws_g_proof") is True


def test_anti_gaming_mutation_probe_fails_gaming_passes_honest(tmp_path: Path) -> None:
    honest = ae.mutation_probe(_complete_delivery(tmp_path / "honest", test=_HONEST_TEST))
    assert honest.status == "pass"

    gaming = ae.mutation_probe(_complete_delivery(tmp_path / "gaming", test=_GAMING_TEST))
    assert gaming.status == "fail"
    assert "green" in gaming.detail.lower()


def test_anti_gaming_gaming_suite_denies_a_whole_delivery_green(tmp_path: Path) -> None:
    root = _complete_delivery(tmp_path / "d", test=_GAMING_TEST)
    card = ae.score_delivery(root, enabled=True)
    assert _status_of(card, "anti_gaming_probe") == "fail"
    assert card.passed is False


def test_anti_gaming_empty_delivery_earns_no_credit(tmp_path: Path) -> None:
    empty = tmp_path / "empty" / "fixtures"
    empty.mkdir(parents=True)
    card = ae.score_delivery(tmp_path / "empty", enabled=True)
    assert {d.status for d in card.dimensions} == {"skipped"}
    assert card.passed is False


def test_anti_gaming_d6_test_tension_is_not_correctness_d5_is_the_backstop(tmp_path: Path) -> None:
    root = _complete_delivery(tmp_path / "d", test=_WEAK_TENSION_TEST)


    _write(root / "fixtures" / "golden-eval.json", json.dumps({"accuracy": 0.55, "bar": 0.8}))

    card = ae.score_delivery(root, enabled=True)

    assert _status_of(card, "anti_gaming_probe") == "pass"

    assert _status_of(card, "golden_eval") == "fail"


    assert card.passed is False
    assert card.verdict == "incomplete"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
