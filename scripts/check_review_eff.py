#!/usr/bin/env python3

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import metrics_lib
import wave_kpi
from _paths import ROOT


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description='check_review_eff.py — T6 review-efficiency reader.')
    ap.add_argument("--events", type=Path, default=ROOT / "board" / ".events.jsonl")
    ap.add_argument("--max-rework-rate", type=float, default=None,
                    help="if set, fail when rework_rate exceeds this (default: report only)")
    args = ap.parse_args(argv)

    eff = metrics_lib.review_efficiency(wave_kpi.read_events(str(args.events)))
    if eff is None:
        print("T6 review efficiency: unmeasured — no reviews logged yet. Gate inert (loop off).")
        return 0

    summary = (
        f"T6: median review cycle {eff['median_cycle_s'] / 60:.1f} min, "
        f"rework rate {eff['rework_rate']:.3f} over {eff['reviews']} review(s) "
        f"({eff['completed']} completed)."
    )
    if args.max_rework_rate is not None and eff["rework_rate"] > args.max_rework_rate:
        sys.stderr.write(f"FAIL: {summary} rework > max {args.max_rework_rate:.2f}.\n")
        return 1
    print(f"OK: {summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
