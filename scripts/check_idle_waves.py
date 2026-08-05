#!/usr/bin/env python3

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import metrics_lib
from _paths import ROOT

DEFAULT_TARGET = 0.15


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description='check_idle_waves.py — T2 idle-wave-rate gate.')
    ap.add_argument("--wave-log", type=Path, default=ROOT / "board" / ".wave-log")
    ap.add_argument("--target", type=float, default=DEFAULT_TARGET)
    args = ap.parse_args(argv)

    rates = metrics_lib.idle_wave_rates(metrics_lib.read_waves(str(args.wave_log)))
    if rates is None:
        print(
            f"T2 idle-wave rate: unmeasured — no waves logged yet. "
            f"Gate inert (loop off); target {args.target:.2f}."
        )
        return 0

    ok = rates["t2a_rate"] <= args.target
    msg = (
        f"{'OK' if ok else 'FAIL'}: T2a idle rate {rates['t2a_rate']:.3f} "
        f"({'<=' if ok else '>'} target {args.target:.2f}); "
        f"T2b blocked {rates['t2b_rate']:.3f} (informational) over {rates['total']} waves."
    )
    if ok:
        print(msg)
        return 0
    sys.stderr.write(msg + "\n")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
