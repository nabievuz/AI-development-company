#!/usr/bin/env python3

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import metrics_lib
import wave_kpi
from _paths import ROOT

DEFAULT_TARGET = 0.25


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description='check_model_mix.py — T4 cost/model-mix gate.')
    ap.add_argument("--events", type=Path, default=ROOT / "board" / ".events.jsonl")
    ap.add_argument("--target", type=float, default=DEFAULT_TARGET)
    args = ap.parse_args(argv)

    mix = metrics_lib.model_mix(wave_kpi.read_events(str(args.events)))
    if mix is None:
        print(
            f"T4 cost/model-mix: unmeasured — no completed work with a model yet. "
            f"Gate inert (loop off); target {args.target:.2f}."
        )
        return 0

    ok = mix["ratio"] >= args.target
    msg = (
        f"{'OK' if ok else 'FAIL'}: T4 low-cost share {mix['ratio']:.3f} "
        f"({'>=' if ok else '<'} target {args.target:.2f}) over {mix['total']} completed task(s)."
    )
    if ok:
        print(msg)
        return 0
    sys.stderr.write(msg + "\n")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
