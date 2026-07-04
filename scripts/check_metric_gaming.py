#!/usr/bin/env python3
"""check_metric_gaming.py — anti-gaming rule.

T1-T6 may count a unit of work ONLY if it ended in a merged PR + green CI + a T7
pass. This flags counted completions that lack that evidence — busy/concurrency
without delivered value must not inflate the metrics (Goodhart defence). It also
reports the orthogonal **T1b** high-impact-completion rate (T7 >= 0.90) for HUMAN
oversight only; T1b is never a target agents see, so it cannot be gamed. Reads the
event store; inert (exit 0) when there are no completions yet.

Committed-evidence gate (P13 / DAS-1460): a run whose completion is COUNTED
toward the KPIs must also leave a durable, git-auditable snapshot at
``metrics/evidence/<run_id>.json`` (written by ``scripts/snapshot_evidence.py``).
A counted-completion run with **no** committed evidence file FAILS the gate — you
cannot count work toward the metrics without leaving committed proof (a Goodhart
defence complementing R-9). Completions without a ``run_id`` cannot be keyed to a
snapshot and are out of scope for this requirement.

Exit codes: 0 = no gaming OR unmeasured, 1 = counted busywork OR a counted run
missing committed evidence, 2 = usage error.

Usage:
    python3 scripts/check_metric_gaming.py [--events board/.events.jsonl]
                                           [--evidence-dir metrics/evidence]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import metrics_lib
import snapshot_evidence
import wave_kpi
from _paths import ROOT


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
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

    # Committed-evidence gate (P13): every counted run must have a committed
    # metrics/evidence/<run_id>.json snapshot. Missing proof => counted work is
    # not auditable from git history => fail (non-zero).
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
