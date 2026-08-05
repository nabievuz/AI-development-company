#!/usr/bin/env python3

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import wave_kpi
from _paths import ROOT

DEFAULT_TARGET = 0.60


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description='check_busy_fraction.py — T1 busy-fraction gate.')
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
