#!/usr/bin/env python3

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import metrics_lib
import snapshot_evidence
import wave_kpi
from _paths import ROOT


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description='check_metric_gaming.py — anti-gaming rule.')
    ap.add_argument("--events", type=Path, default=ROOT / "board" / ".events.jsonl")
    ap.add_argument(
        "--evidence-dir",
        type=Path,
        default=snapshot_evidence.EVIDENCE_DIR,
        help="committed evidence directory (default: metrics/evidence)",
    )
    args = ap.parse_args(argv)

    events = wave_kpi.read_events(str(args.events))
    gaming = metrics_lib.gaming_violations(events)
    if gaming is None:
        print("Anti-gaming: unmeasured — no completions yet. Gate inert (loop off).")
        return 0

    t1b = metrics_lib.t1b_high_impact(events)
    t1b_note = f" T1b high-impact rate {t1b['rate']:.3f} (human-oversight)." if t1b else ""

    if gaming["violations"]:
        sys.stderr.write("FAIL: anti-gaming (R-9) — counted work without delivered value:\n")
        for v in gaming["violations"]:
            sys.stderr.write(f"  - {v}\n")
        sys.stderr.write(
            f"\n{len(gaming['violations'])} of {gaming['completions']} completion(s) gamed.{t1b_note}\n"
        )
        return 1


    missing = snapshot_evidence.missing_evidence_runs(events, args.evidence_dir)
    if missing:
        sys.stderr.write(
            "FAIL: committed-evidence (P13) — counted completion(s) without a "
            "committed metrics/evidence/<run_id>.json snapshot:\n"
        )
        for rid in missing:
            sys.stderr.write(f"  - {rid}: no committed evidence file\n")
        sys.stderr.write(
            f"\n{len(missing)} counted run(s) missing committed evidence. Run "
            "`python3 scripts/snapshot_evidence.py` and commit the result.\n"
        )
        return 1

    print(
        f"OK: {gaming['completions']} completion(s), all merged+CI+T7 with "
        f"committed evidence.{t1b_note}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
