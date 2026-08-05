
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS = _REPO_ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import check_attestation as ca
import check_ledger as cl
import wave_runner as wr

_ROUTING = _REPO_ROOT / "board" / "ROUTING.md"
_GUARDRAILS = _REPO_ROOT / "governance" / "guardrails"
_ATTEST_DIR = _REPO_ROOT / "metrics" / "attestations"
_EVIDENCE_DIR = _REPO_ROOT / "metrics" / "evidence"

_WAVE_TS = "2026-07-04T12:00:00Z"
_WAVE_TS2 = "2026-07-04T13:00:00Z"
_END_TS = "2026-07-04T12:10:00Z"


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


def _drive(tmp: Path, run_id: str, created_at: str) -> wr.WaveAttestation:
    board = tmp / "board" / "tickets"
    _write_ticket(board, "DAS-9001", "backend-eng-1")
    _write_ticket(board, "DAS-9002", "backend-eng-2")


    common = {
        "outcome": "success", "merged_pr": True, "ci_status": "green",
        "t7_pass": True, "t7_score": 0.95, "start": _WAVE_TS, "end": _END_TS,
        "final_status": "done", "output": "done; tests green.",
    }
    plan = wr.WavePlan(
        run_id=run_id, wave=1, goal="organism-ws8-attest", engine_version="1.0.0",
        tickets=[wr.TicketPlan("DAS-9001", "backend-eng-1", "opus"),
                 wr.TicketPlan("DAS-9002", "backend-eng-2", "sonnet")],
    )
    results = wr.WaveResults(tickets=[wr.TicketResult(ticket_id="DAS-9001", **common),
                                      wr.TicketResult(ticket_id="DAS-9002", **common)])
    att = wr.run_wave(
        plan, wr.replay_executor(results.tickets), created_at=created_at,
        store_path=tmp / "events.jsonl", runs_dir=tmp / "runs",
        attest_dir=tmp / "attest", ledger_path=tmp / "board" / "wave-ledger.jsonl",
        evidence_dir=tmp / "evidence",
        tickets_dir=board, board_dir=board,
        routing_path=_ROUTING, guardrails_dir=_GUARDRAILS,
    )
    assert att is not None
    return att


def test_committed_attestations_hold_no_fixture_evidence() -> None:
    if not _ATTEST_DIR.is_dir():
        return
    for path in sorted(_ATTEST_DIR.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert not str(payload.get("run_id", "")).startswith(cl.FIXTURE_RUN_ID_PREFIX), (
            f"{path} is fixture-generated evidence committed as if it were real"
        )


def test_committed_attestations_verify(capsys) -> None:
    rc = ca.main(["--attest-dir", str(_ATTEST_DIR), "--evidence-dir", str(_EVIDENCE_DIR)])
    assert rc == 0


def test_inert_when_no_attestations(tmp_path: Path, capsys) -> None:
    empty = tmp_path / "attest"
    empty.mkdir()
    rc = ca.main(["--attest-dir", str(empty), "--evidence-dir", str(tmp_path / "ev")])
    assert rc == 0
    assert "inert" in capsys.readouterr().out


def test_inert_when_attest_dir_absent(tmp_path: Path) -> None:
    rc = ca.main(["--attest-dir", str(tmp_path / "nope"), "--evidence-dir", str(tmp_path)])
    assert rc == 0


def test_fresh_receipt_passes(tmp_path: Path) -> None:
    _drive(tmp_path, "01JWAVE0000000000000000001", _WAVE_TS)
    rc = ca.main(["--attest-dir", str(tmp_path / "attest"),
                  "--evidence-dir", str(tmp_path / "evidence")])
    assert rc == 0


def test_delivery_receipt_is_not_read_as_a_wave_attestation(tmp_path: Path) -> None:
    _drive(tmp_path, "01JWAVE0000000000000000001", _WAVE_TS)
    attest = tmp_path / "attest"


    (attest / "01JWAVE0000000000000000001.delivery.json").write_text(
        json.dumps({"schema": "daslab.delivery_attestation.v1", "verdict": "complete"}),
        encoding="utf-8",
    )
    rc = ca.main(["--attest-dir", str(attest),
                  "--evidence-dir", str(tmp_path / "evidence")])
    assert rc == 0


def test_tampered_counts_fail(tmp_path: Path) -> None:
    att = _drive(tmp_path, "01JWAVE0000000000000000001", _WAVE_TS)
    payload = json.loads(att.path.read_text())
    payload["counts"]["counted_completions"] = 99
    att.path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    rc = ca.main(["--attest-dir", str(tmp_path / "attest"),
                  "--evidence-dir", str(tmp_path / "evidence")])
    assert rc == 1


def test_tampered_mechanic_flag_fails(tmp_path: Path) -> None:
    att = _drive(tmp_path, "01JWAVE0000000000000000001", _WAVE_TS)
    payload = json.loads(att.path.read_text())
    payload["mechanics"]["checkpoint_open"] = False
    att.path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    errs = ca.verify_completeness(payload, tmp_path / "evidence")
    assert any("checkpoint_open" in e for e in errs)
    rc = ca.main(["--attest-dir", str(tmp_path / "attest"),
                  "--evidence-dir", str(tmp_path / "evidence")])
    assert rc == 1


def test_missing_ticket_run_events_fail(tmp_path: Path) -> None:

    att = _drive(tmp_path, "01JWAVE0000000000000000001", _WAVE_TS)
    payload = json.loads(att.path.read_text())
    payload["mechanics"]["events_emitted"]["run_end"] = 1
    errs = ca.verify_completeness(payload, tmp_path / "evidence")
    assert any("run_end" in e for e in errs)


def test_missing_committed_evidence_fails(tmp_path: Path) -> None:
    _drive(tmp_path, "01JWAVE0000000000000000001", _WAVE_TS)
    empty_ev = tmp_path / "no-evidence"
    empty_ev.mkdir()
    rc = ca.main(["--attest-dir", str(tmp_path / "attest"), "--evidence-dir", str(empty_ev)])
    assert rc == 1


def test_missing_ledger_digest_fails(tmp_path: Path) -> None:
    att = _drive(tmp_path, "01JWAVE0000000000000000001", _WAVE_TS)
    payload = json.loads(att.path.read_text())
    del payload["ledger_digest"]
    errs = ca.verify_completeness(payload, tmp_path / "evidence")
    assert any("ledger_digest" in e for e in errs)


def test_dangling_chain_fails(tmp_path: Path) -> None:
    first = _drive(tmp_path, "01JWAVE0000000000000000001", _WAVE_TS)
    second = _drive(tmp_path, "01JWAVE0000000000000000002", _WAVE_TS2)
    assert second.prev_hash == first.self_hash
    first.path.unlink()
    rc = ca.main(["--attest-dir", str(tmp_path / "attest"),
                  "--evidence-dir", str(tmp_path / "evidence")])
    assert rc == 1


def test_chain_ok_across_two_waves(tmp_path: Path) -> None:
    _drive(tmp_path, "01JWAVE0000000000000000001", _WAVE_TS)
    _drive(tmp_path, "01JWAVE0000000000000000002", _WAVE_TS2)
    rc = ca.main(["--attest-dir", str(tmp_path / "attest"),
                  "--evidence-dir", str(tmp_path / "evidence")])
    assert rc == 0


def test_corrupt_json_fails(tmp_path: Path) -> None:
    attest = tmp_path / "attest"
    attest.mkdir()
    (attest / "01JBROKEN0000000000000001.json").write_text("{not json", encoding="utf-8")
    rc = ca.main(["--attest-dir", str(attest), "--evidence-dir", str(tmp_path / "ev")])
    assert rc == 1


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
