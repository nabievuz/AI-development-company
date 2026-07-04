#!/usr/bin/env python3
"""replay_qa.py — Replay-QA / recovery-drill harness.

Replays each run's recorded routing transitions deterministically and verifies the
transition chain is intact. A broken chain (a from_status that does not match the
previous to_status, or an out-of-order / invalid-status resume) is a CORRUPTED
resume — exactly the failure T5 recovery reliability guards against (guardrail:
zero corrupted resumes). Optionally emits recovery_drill events that feed
check_recovery.py (T5). Inert (exit 0) when there are no runs to replay.

Exit codes: 0 = all runs replay cleanly OR unmeasured, 1 = a corrupted replay, 2 = usage.

Usage:
    python3 scripts/replay_qa.py [--events board/.events.jsonl] [--emit board/.events.jsonl]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import wave_kpi
from _paths import ROOT

VALID_STATUSES = {"backlog", "todo", "in_progress", "blocked", "in_review", "done"}


def _run_key(ev: dict) -> str:
    return str(ev.get("run_id") or ev.get("ticket_id") or "")


def group_runs(events: list[dict]) -> dict[str, list[dict]]:
    runs: dict[str, list[dict]] = {}
    for ev in events:
        if ev.get("event_type") != "routing_decision":
            continue
        key = _run_key(ev)
        if key:
            runs.setdefault(key, []).append(ev)
    return runs


def replay_run(transitions: list[dict]) -> dict:
    """Replay one run's transitions in order; detect a corrupted resume (broken chain)."""
    ordered = sorted(transitions, key=lambda e: str(e.get("created_at", "")))
    prev_to = None
    steps = 0
    for t in ordered:
        frm, to = t.get("from_status"), t.get("to_status")
        # A missing/None to_status must NOT silently disable the chain check — it is
        # itself a corrupted resume (the resume point is unknown).
        if to is None or to not in VALID_STATUSES:
            return {"replayable": False, "corrupted": True, "reason": f"invalid/missing to_status {to!r}"}
        if frm is not None and frm not in VALID_STATUSES:
            return {"replayable": False, "corrupted": True, "reason": f"invalid from_status {frm!r}"}
        if prev_to is not None and frm != prev_to:
            return {"replayable": False, "corrupted": True, "reason": f"broken chain {prev_to!r} -> {frm!r}"}
        prev_to = to
        steps += 1
    return {"replayable": True, "corrupted": False, "final_status": prev_to, "steps": steps}


def drill(events: list[dict]) -> dict:
    results = {k: replay_run(v) for k, v in group_runs(events).items()}
    return {
        "runs": len(results),
        "replayable": sum(1 for r in results.values() if r["replayable"]),
        "corrupted": [k for k, r in results.items() if r["corrupted"]],
        "results": results,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--events", type=Path, default=ROOT / "board" / ".events.jsonl")
    ap.add_argument("--emit", type=Path, default=None, help="append recovery_drill events to this store (T5)")
    args = ap.parse_args(argv)

    summary = drill(wave_kpi.read_events(str(args.events)))
    if summary["runs"] == 0:
        print(f"Replay-QA: unmeasured — no runs to replay ({args.events}). Inert (loop off).")
        return 0

    if args.emit:
        now = datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        with open(args.emit, "a", encoding="utf-8") as fh:
            for key, r in summary["results"].items():
                fh.write(json.dumps({
                    "event_type": "recovery_drill", "ticket_id": "DAS-REPLAY", "run_id": key,
                    "created_at": now, "outcome": "success" if r["replayable"] else "fail",
                    "corrupted": r["corrupted"],
                }) + "\n")

    if summary["corrupted"]:
        sys.stderr.write("FAIL: replay-QA found corrupted resume(s) (T5 / zero-corrupted guardrail):\n")
        for k in summary["corrupted"]:
            sys.stderr.write(f"  - run {k}: {summary['results'][k]['reason']}\n")
        return 1

    print(f"OK: {summary['replayable']}/{summary['runs']} run(s) replay cleanly, 0 corrupted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
