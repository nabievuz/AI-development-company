#!/usr/bin/env python3

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

import wave_runner as wr
from _paths import ROOT


SAMPLE_RUN_ID = "01KWS8ATTEST00000000000001"
_WAVE_TS = "2026-07-04T12:00:00Z"
_RUN_END_TS = "2026-07-04T12:10:00Z"

_ROUTING = ROOT / "board" / "ROUTING.md"
_GUARDRAILS = ROOT / "governance" / "guardrails"
_ATTEST_DIR = ROOT / "metrics" / "attestations"
_EVIDENCE_DIR = ROOT / "metrics" / "evidence"

_LEDGER_PATH = wr.LEDGER_PATH


def _write_ticket(board_dir: Path, ticket_id: str, assignee: str) -> None:
    board_dir.mkdir(parents=True, exist_ok=True)
    (board_dir / f"{ticket_id}-synthetic.md").write_text(
        "---\n"
        f"id: {ticket_id}\n"
        "title: Synthetic attestation-sample fixture\n"
        "status: in_progress\n"
        f"assignee: {assignee}\n"
        "author: cto\n"
        "dept: engineering\n"
        "priority: p1\n"
        "---\n\n"
        "## Description\nSynthetic ticket backing the committed attestation sample.\n",
        encoding="utf-8",
    )


def _plan() -> wr.WavePlan:
    return wr.WavePlan(
        run_id=SAMPLE_RUN_ID,
        wave=1,
        goal="organism-ws8-attest",
        engine_version=(ROOT / "VERSION").read_text(encoding="utf-8").strip(),
        tickets=[
            wr.TicketPlan("DAS-9001", role="backend-eng-1", model="opus"),
            wr.TicketPlan("DAS-9002", role="backend-eng-2", model="sonnet"),
        ],
    )


def _results() -> wr.WaveResults:
    common = {
        "outcome": "success",
        "merged_pr": True,
        "ci_status": "green",
        "t7_pass": True,
        "t7_score": 0.95,
        "start": _WAVE_TS,
        "end": _RUN_END_TS,
        "final_status": "done",
        "output": "Implemented the change; all tests green.",
    }
    return wr.WaveResults(
        tickets=[
            wr.TicketResult(ticket_id="DAS-9001", **common),
            wr.TicketResult(ticket_id="DAS-9002", **common),
        ],
    )


def _materialise_sample_ledger(sample_line: str, ledger_path: Path = _LEDGER_PATH) -> None:
    existing = []
    if ledger_path.exists():
        existing = [ln for ln in ledger_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    tail = existing[1:]
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path.write_text("\n".join([sample_line, *tail]) + "\n", encoding="utf-8")


def generate(
    attest_dir: Path = _ATTEST_DIR,
    evidence_dir: Path = _EVIDENCE_DIR,
    ledger_path: Path = _LEDGER_PATH,
) -> wr.WaveAttestation:
    with tempfile.TemporaryDirectory(prefix="daslab-attest-sample-") as tmp:
        tmp_path = Path(tmp)
        board = tmp_path / "board" / "tickets"
        _write_ticket(board, "DAS-9001", "backend-eng-1")
        _write_ticket(board, "DAS-9002", "backend-eng-2")


        tmp_ledger = tmp_path / "wave-ledger.jsonl"
        att = wr.run_wave(
            _plan(),
            _results(),
            created_at=_WAVE_TS,
            store_path=tmp_path / "events.jsonl",
            runs_dir=tmp_path / "runs",
            attest_dir=attest_dir,
            ledger_path=tmp_ledger,
            evidence_dir=evidence_dir,
            tickets_dir=board,
            board_dir=board,
            routing_path=_ROUTING,
            guardrails_dir=_GUARDRAILS,
        )
        sample_line = tmp_ledger.read_text(encoding="utf-8").splitlines()[-1]
    assert att is not None
    _materialise_sample_ledger(sample_line, ledger_path)
    return att


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description='gen_sample_attestation.py — (re)produce the committed sample wave-attestation.')
    ap.add_argument(
        "--check",
        action="store_true",
        help="verify the committed sample is byte-identical to a fresh regeneration",
    )
    args = ap.parse_args(argv)

    att_path = wr.attestation_path(SAMPLE_RUN_ID, _ATTEST_DIR)
    if args.check:
        if not att_path.is_file():
            sys.stderr.write(f"missing committed sample attestation: {att_path}\n")
            return 1
        if not _LEDGER_PATH.is_file():
            sys.stderr.write(f"missing committed sample wave-ledger: {_LEDGER_PATH}\n")
            return 1
        before_att = att_path.read_text(encoding="utf-8")
        before_ledger = _LEDGER_PATH.read_text(encoding="utf-8")
        generate()
        stale = []
        if att_path.read_text(encoding="utf-8") != before_att:
            stale.append("attestation (metrics/attestations/)")
        if _LEDGER_PATH.read_text(encoding="utf-8") != before_ledger:
            stale.append("wave-ledger (board/wave-ledger.jsonl)")
        if stale:
            sys.stderr.write(
                "committed sample is STALE [" + ", ".join(stale) + "] — run "
                "`python3 scripts/gen_sample_attestation.py` and commit.\n"
            )
            return 1
        print(
            "OK: committed sample attestation + wave-ledger are up to date "
            f"({att_path.name})."
        )
        return 0

    att = generate()
    print(f"wrote sample attestation: {att.path}")
    for rid in att.payload["evidence"]["run_ids"]:
        print(f"  + evidence: metrics/evidence/{rid}.json")
    print(f"  + wave-ledger entry: board/{_LEDGER_PATH.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
