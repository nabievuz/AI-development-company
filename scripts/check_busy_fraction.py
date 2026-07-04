#!/usr/bin/env python3
"""check_busy_fraction.py — T1 busy-fraction gate.

T1 = useful agent time / available time, read from the live DGO-X event store
(``board/.events.jsonl``) via ``wave_kpi``. Target >= 0.60.

In a loop-off / no-live-waves world there is no data yet, so the gate is INERT
(exit 0, "unmeasured") — never a fabricated pass or fail. Once real
``run_start`` / ``run_end`` events exist it enforces T1 >= target. The guardrail
is that raising T1 must never reduce T7 (enforced by check_t7_quality.py).

Exit codes: 0 = T1 >= target OR unmeasured, 1 = T1 below target, 2 = usage/IO error.

Usage:
    python3 scripts/check_busy_fraction.py [--events board/.events.jsonl] [--target 0.60]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import wave_kpi
from _paths import ROOT

DEFAULT_TARGET = 0.60


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--events", type=Path, default=ROOT / "board" / ".events.jsonl")
    ap.add_argument("--target", type=float, default=DEFAULT_TARGET)
    args = ap.parse_args(argv)

    events = wave_kpi.read_events(str(args.events))
    fraction, stats = wave_kpi.busy_fraction_from_events(events)

    if fraction is None:
        print(
            f"T1 busy fraction: unmeasured — no paired run events yet "
            f"({stats['events']} events, {stats['runs_completed']} completed run(s)). "
            f"Gate inert (loop off); target {args.target:.2f}."
        )
        return 0

    ok = fraction >= args.target
    msg = (
        f"{'OK' if ok else 'FAIL'}: T1 busy fraction {fraction:.3f} "
        f"({'>=' if ok else '<'} target {args.target:.2f}) "
        f"over {stats['runs_completed']} completed run(s)."
    )
    if ok:
        print(msg)
        return 0
    sys.stderr.write(msg + "\n")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
