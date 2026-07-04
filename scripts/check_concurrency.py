#!/usr/bin/env python3
"""check_concurrency.py — T3 effective-concurrency gate.

T3 = median & p95 of concurrently-active runs, target >= 6 (on the median).
Reads the event store run_start/run_end intervals; inert (exit 0) when there are
no paired run events yet. Guardrail: more concurrency must not raise conflicts /
rework (watched by T6/T7), never a fabricated number.

Exit codes: 0 = median >= target OR unmeasured, 1 = below target, 2 = usage error.

Usage:
    python3 scripts/check_concurrency.py [--events board/.events.jsonl] [--target 6]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import metrics_lib
import wave_kpi
from _paths import ROOT

DEFAULT_TARGET = 6.0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--events", type=Path, default=ROOT / "board" / ".events.jsonl")
    ap.add_argument("--target", type=float, default=DEFAULT_TARGET)
    args = ap.parse_args(argv)

    stats = metrics_lib.concurrency_stats(wave_kpi.read_events(str(args.events)))
    if stats is None:
        print(
            f"T3 effective concurrency: unmeasured — no paired run events yet. "
            f"Gate inert (loop off); target {args.target:.1f}."
        )
        return 0

    ok = stats["median"] >= args.target
    msg = (
        f"{'OK' if ok else 'FAIL'}: T3 median concurrency {stats['median']:.1f} "
        f"({'>=' if ok else '<'} target {args.target:.1f}), p95 {stats['p95']:.1f} "
        f"over {stats['samples']} run(s)."
    )
    if ok:
        print(msg)
        return 0
    sys.stderr.write(msg + "\n")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
