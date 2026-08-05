#!/usr/bin/env python3

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

import check_ledger as cl
import wave_runner as wr
from _paths import ROOT

FIXTURE_RUN_ID: str = cl.FIXTURE_RUN_ID_PREFIX + "0000000000000000000000001"

FIXTURE_TICKET_IDS: tuple[str, ...] = ("DAS-9901", "DAS-9902")

_FIXTURE_TS = "2026-07-04T12:00:00Z"
_FIXTURE_END_TS = "2026-07-04T12:10:00Z"

_GUARDRAILS = ROOT / "governance" / "guardrails"

COMMITTED_EVIDENCE_PATHS: tuple[Path, ...] = (
    ROOT / "metrics" / "attestations",
    ROOT / "metrics" / "evidence",
    ROOT / "board" / "wave-ledger.jsonl",
)


class FixtureNamespaceViolation(RuntimeError):
    pass


def _reject_committed_target(label: str, target: Path) -> None:
    resolved = target.resolve()
    for committed in COMMITTED_EVIDENCE_PATHS:
        committed = committed.resolve()
        if resolved == committed or committed in resolved.parents:
            raise FixtureNamespaceViolation(
                f"{label}={target} points at the repository's committed evidence "
                f"({committed}). Fixtures are never committed evidence: write them to a "
                "throwaway directory instead."
            )


def _write_fixture_ticket(board_dir: Path, ticket_id: str, assignee: str) -> None:
    board_dir.mkdir(parents=True, exist_ok=True)
    (board_dir / f"{ticket_id}.md").write_text(
        "---\n"
        f"id: {ticket_id}\n"
        "title: Fixture ticket (not a real board ticket)\n"
        "status: in_progress\n"
        f"assignee: {assignee}\n"
        "author: cto\n"
        "dept: engineering\n"
        "priority: p1\n"
        "---\n\nFixture body.\n",
        encoding="utf-8",
    )


def _plan(run_id: str) -> wr.WavePlan:
    return wr.WavePlan(
        run_id=run_id,
        wave=1,
        goal="fixture-only",
        engine_version=(ROOT / "VERSION").read_text(encoding="utf-8").strip(),
        tickets=[
            wr.TicketPlan(FIXTURE_TICKET_IDS[0], role="backend-eng-1", model="opus"),
            wr.TicketPlan(FIXTURE_TICKET_IDS[1], role="backend-eng-2", model="sonnet"),
        ],
    )


def _results() -> list[wr.TicketResult]:
    common = {
        "outcome": "success",
        "merged_pr": True,
        "ci_status": "green",
        "t7_pass": True,
        "t7_score": 0.95,
        "start": _FIXTURE_TS,
        "end": _FIXTURE_END_TS,
        "final_status": "done",
        "output": "fixture result — no work was performed",
    }
    return [wr.TicketResult(ticket_id=tid, **common) for tid in FIXTURE_TICKET_IDS]


def generate_fixture(
    *,
    attest_dir: Path,
    evidence_dir: Path,
    ledger_path: Path,
    run_id: str = FIXTURE_RUN_ID,
    created_at: str = _FIXTURE_TS,
) -> wr.WaveAttestation:
    if not cl.is_fixture_run_id(run_id):
        raise FixtureNamespaceViolation(
            f"fixture run_id must start with {cl.FIXTURE_RUN_ID_PREFIX!r}; got {run_id!r}"
        )
    _reject_committed_target("--attest-dir", attest_dir)
    _reject_committed_target("--evidence-dir", evidence_dir)
    _reject_committed_target("--ledger-path", ledger_path)

    with tempfile.TemporaryDirectory(prefix="daslab-attest-fixture-") as tmp:
        tmp_path = Path(tmp)
        board = tmp_path / "board" / "tickets"
        _write_fixture_ticket(board, FIXTURE_TICKET_IDS[0], "backend-eng-1")
        _write_fixture_ticket(board, FIXTURE_TICKET_IDS[1], "backend-eng-2")
        att = wr.run_wave(
            _plan(run_id),
            wr.replay_executor(_results()),
            created_at=created_at,
            store_path=tmp_path / "events.jsonl",
            runs_dir=tmp_path / "runs",
            attest_dir=attest_dir,
            ledger_path=ledger_path,
            evidence_dir=evidence_dir,
            tickets_dir=board,
            board_dir=board,
            guardrails_dir=_GUARDRAILS,
        )
    if att is None:
        raise RuntimeError("wave_runner.run_wave produced no attestation for the fixture")
    return att


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=(
            "gen_sample_attestation.py — build a THROWAWAY wave-attestation fixture. "
            "Fixtures live in the reserved "
            f"{cl.FIXTURE_RUN_ID_PREFIX!r} run-id namespace and the real verifiers "
            "(scripts/check_ledger.py --wave-ledger, scripts/check_evidence_gate.py) "
            "reject them as evidence. Writing into the repository's committed "
            "evidence is refused."
        )
    )
    ap.add_argument("--out-dir", type=Path, required=True, help="throwaway directory to write the fixture into")
    args = ap.parse_args(argv)

    out = args.out_dir
    try:
        att = generate_fixture(
            attest_dir=out / "attestations",
            evidence_dir=out / "evidence",
            ledger_path=out / "wave-ledger.jsonl",
        )
    except FixtureNamespaceViolation as exc:
        sys.stderr.write(f"REFUSED: {exc}\n")
        return 2

    print(f"wrote FIXTURE attestation (not evidence): {att.path}")
    print(f"  + fixture wave-ledger: {out / 'wave-ledger.jsonl'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
