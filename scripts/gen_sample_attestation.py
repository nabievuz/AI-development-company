#!/usr/bin/env python3
"""gen_sample_attestation.py — (re)produce the committed sample wave-attestation.

ORGANISM WS8 ATTEST (ADR-0031 / DAS-1500) + WS9 HARNESS (ADR-0032 / DAS-1505).
``check_attestation.py`` is a fail-closed CI gate, but it is INERT when no
attestation is committed. To give the gate TEETH on real data, this script drives a
synthetic-but-real wave through the REAL :func:`wave_runner.run_wave` — the exact
production seam DAS-1499 shipped — and commits the resulting receipt + its redacted
evidence snapshots into the TRACKED ``metrics/attestations/`` and
``metrics/evidence/`` directories.  The SAME ``run_wave`` call co-produces the
matching entry in the TRACKED ``board/wave-ledger.jsonl`` (ADR-0032 §1): this script
materialises that sample entry (the genesis line of the ledger chain) so the
reconciliation gate (DAS-1506) has committed teeth too.

The wave is deterministic: fixed ``run_id``, fixed caller-supplied timestamps, two
synthetic tickets routed to real roles. Re-running this script is idempotent — it
reproduces byte-identical committed files (a clean ``git diff``), so a reviewer can
regenerate and confirm the sample was genuinely produced by ``run_wave`` and never
hand-edited.  The ledger entry's ``attestation_hash`` is the SHA-256 of the committed
sample attestation FILE, keeping the two committed records in lock-step.

The event store + progress-ledger land in a throwaway temp tree (runtime state is
gitignored); only the attestation + evidence and the co-produced wave-ledger entry —
the committed, git-auditable proof — are written under ``metrics/`` and ``board/``.

Usage:
    python3 scripts/gen_sample_attestation.py            # (re)write the sample
    python3 scripts/gen_sample_attestation.py --check    # verify it is up to date
"""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

import wave_runner as wr
from _paths import ROOT

#: Deterministic, obviously-synthetic run id (26-char ULID shape, Crockford safe).
SAMPLE_RUN_ID = "01KWS8ATTEST00000000000001"
_WAVE_TS = "2026-07-04T12:00:00Z"
_RUN_END_TS = "2026-07-04T12:10:00Z"

_ROUTING = ROOT / "board" / "ROUTING.md"
_GUARDRAILS = ROOT / "governance" / "guardrails"
_ATTEST_DIR = ROOT / "metrics" / "attestations"
_EVIDENCE_DIR = ROOT / "metrics" / "evidence"
#: Committed TRACKED wave-ledger the sample entry lands in (ADR-0032 §1 / DAS-1505).
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
    """Write the deterministic sample entry as the genesis (first) line of the ledger.

    The sample is committed at regime start, so it is line 0 of the chain; any real
    wave entries appended after it (which chain off the sample's deterministic
    ``self_hash``) are preserved as the tail.  Idempotent: re-running replaces line 0
    with the byte-identical sample line and leaves the rest untouched.
    """
    existing = []
    if ledger_path.exists():
        existing = [ln for ln in ledger_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    tail = existing[1:]  # everything after the (old) sample line
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path.write_text("\n".join([sample_line, *tail]) + "\n", encoding="utf-8")


def generate(
    attest_dir: Path = _ATTEST_DIR,
    evidence_dir: Path = _EVIDENCE_DIR,
    ledger_path: Path = _LEDGER_PATH,
) -> wr.WaveAttestation:
    """Drive the synthetic wave through ``run_wave``, committing receipt + evidence + ledger."""
    with tempfile.TemporaryDirectory(prefix="daslab-attest-sample-") as tmp:
        tmp_path = Path(tmp)
        board = tmp_path / "board" / "tickets"
        _write_ticket(board, "DAS-9001", "backend-eng-1")
        _write_ticket(board, "DAS-9002", "backend-eng-2")
        # Direct the ledger co-write to a THROWAWAY temp file so it is a clean
        # genesis-prev entry (deterministic), then materialise the committed sample
        # line — never append blindly to the committed ledger (that would duplicate).
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
    assert att is not None  # organism_emit defaults on → a receipt is always returned
    _materialise_sample_ledger(sample_line, ledger_path)
    return att


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
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
