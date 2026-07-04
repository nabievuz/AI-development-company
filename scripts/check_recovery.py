#!/usr/bin/env python3
"""check_recovery.py — T5 recovery-reliability gate.

T5 = successful_replays / recovery_drills, target >= 0.99. Guardrail: **zero
corrupted resumes** — any corrupted drill fails the gate regardless of the ratio.
Reads ``recovery_drill`` events; inert (exit 0) when no drills have run.

Exit codes: 0 = >=target and zero corrupted (or unmeasured), 1 = below / corrupted, 2 = usage.

Usage:
    python3 scripts/check_recovery.py [--events board/.events.jsonl] [--target 0.99]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import metrics_lib
import wave_kpi
from _paths import ROOT

DEFAULT_TARGET = 0.99


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--events", type=Path, default=ROOT / "board" / ".events.jsonl")
    ap.add_argument("--target", type=float, default=DEFAULT_TARGET)
    args = ap.parse_args(argv)

    rec = metrics_lib.recovery_reliability(wave_kpi.read_events(str(args.events)))
    if rec is None:
        print(
            f"T5 recovery reliability: unmeasured — no recovery drills yet. "
            f"Gate inert (loop off); target {args.target:.2f}."
        )
        return 0

    ok = rec["ratio"] >= args.target and rec["corrupted"] == 0
    msg = (
        f"{'OK' if ok else 'FAIL'}: T5 recovery {rec['ratio']:.3f} "
        f"({'>=' if ok else '<'} target {args.target:.2f}), "
        f"corrupted {rec['corrupted']} (must be 0) over {rec['drills']} drill(s)."
    )
    if ok:
        print(msg)
        return 0
    sys.stderr.write(msg + "\n")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
