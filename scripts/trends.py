#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import math
import sys
from pathlib import Path

import wave_kpi
from _paths import ROOT
from dgox.created_at import parse_created_at
from wave_kpi import CliExit


def _parse_iso(ts: str) -> dt.datetime | None:
    return parse_created_at(ts)


def classify_trend(values: list, higher_is_better: bool = True, flat_eps: float = 0.05) -> dict:
    vals: list[float] = []
    for v in values:
        if v is None:
            continue
        try:
            fv = float(v)
        except (TypeError, ValueError):
            continue
        if math.isfinite(fv):
            vals.append(fv)
    if len(vals) < 2:
        return {"direction": "insufficient", "slope": 0.0, "points": len(vals)}
    n = len(vals)
    xmean = (n - 1) / 2
    ymean = sum(vals) / n
    den = sum((i - xmean) ** 2 for i in range(n))
    slope = sum((i - xmean) * (vals[i] - ymean) for i in range(n)) / den if den else 0.0
    if not math.isfinite(slope):
        return {"direction": "insufficient", "slope": 0.0, "points": n}
    if abs(slope) < flat_eps:
        direction = "flat"
    elif (slope > 0) == higher_is_better:
        direction = "improving"
    else:
        direction = "degrading"
    return {"direction": direction, "slope": slope, "points": n}


def dropped_undated_run_ends(events: list[dict]) -> int:
    return sum(
        1 for e in events
        if e.get("event_type") == "run_end" and _parse_iso(str(e.get("created_at", ""))) is None
    )


def throughput_series(events: list[dict], n_windows: int = 5) -> list[float]:
    ts = sorted(
        t for e in events if e.get("event_type") == "run_end"
        for t in (_parse_iso(str(e.get("created_at", ""))),) if t is not None
    )
    if len(ts) < n_windows:
        return []
    start, end = ts[0], ts[-1]
    span = (end - start).total_seconds()
    if span <= 0:
        return []
    width = span / n_windows
    counts = [0] * n_windows
    for t in ts:
        idx = min(int((t - start).total_seconds() / width), n_windows - 1)
        counts[idx] += 1
    return [float(c) for c in counts]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="trends.py",
        description="trends.py — Historical Trend Views.",
        epilog=f"exit codes: {CliExit.HEALTHY.value} trend flat or improving · "
               f"{CliExit.DEGRADED.value} throughput degrading · "
               f"{CliExit.USAGE.value} usage error · "
               f"{CliExit.NO_DATA.value} not enough history to compute a trend",
    )
    ap.add_argument("--events", type=Path, default=ROOT / "board" / ".events.jsonl",
                    help="runtime event store (JSONL)")
    ap.add_argument("--windows", type=int, default=5, help="number of equal-width time windows")
    args = ap.parse_args(argv)

    events = wave_kpi.read_events(str(args.events))
    series = throughput_series(events, max(2, args.windows))
    dropped = dropped_undated_run_ends(events)
    trend = classify_trend(series, higher_is_better=True)
    if dropped:
        print(
            f"NOTE: {dropped} run_end event(s) excluded from the series for a "
            f"missing/non-conforming created_at (DAS-1633)."
        )
    if trend["direction"] == "insufficient":
        sys.stderr.write(
            f"NO DATA: insufficient history ({trend['points']} window(s)); "
            "no throughput trend was computed.\n"
        )
        return CliExit.NO_DATA
    print(
        f"Throughput trend: {trend['direction']} (slope {trend['slope']:+.2f}) "
        f"over {trend['points']} window(s); series {series}."
    )
    return CliExit.DEGRADED if trend["direction"] == "degrading" else CliExit.HEALTHY


if __name__ == "__main__":
    raise SystemExit(main())
