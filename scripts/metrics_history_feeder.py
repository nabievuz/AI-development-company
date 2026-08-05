#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import metrics_lib
import wave_kpi
from _paths import ROOT
from dgox.created_at import DropCounter, parse_created_at

DEFAULT_EVENTS_PATH: Path = ROOT / "board" / ".events.jsonl"
DEFAULT_WAVE_LOG_PATH: Path = ROOT / "board" / ".wave-log"
DEFAULT_HISTORY_PATH: Path = ROOT / "board" / ".metrics-history.jsonl"

__all__ = [
    "compute_window_row",
    "append_history_row",
    "filter_events_by_window",
    "filter_waves_by_date",
    "emit_all_days",
]


def _parse_iso(ts: str) -> datetime | None:
    return parse_created_at(ts)


def filter_events_by_window(
    events: list[dict[str, Any]],
    start: datetime | None,
    end: datetime | None,
    *,
    drop_counter: DropCounter | None = None,
) -> list[dict[str, Any]]:
    if start is None and end is None:
        return list(events)
    result: list[dict[str, Any]] = []
    for ev in events:
        ts = _parse_iso(str(ev.get("created_at", "")))
        if ts is None:
            if drop_counter is not None:
                drop_counter.bump()
            continue
        if start is not None and ts < start:
            continue
        if end is not None and ts > end:
            continue
        result.append(ev)
    return result


def filter_waves_by_date(waves: list[dict], date_str: str) -> list[dict]:
    return [w for w in waves if w.get("date") == date_str]


def _compute_t7_holds(events: list[dict[str, Any]]) -> bool:
    violations = metrics_lib.gaming_violations(events)
    if violations is None:

        return False
    return len(violations["violations"]) == 0


def compute_window_row(
    events: list[dict[str, Any]],
    waves: list[dict],
    *,
    date: str | None = None,
    window_start: str | None = None,
    window_end: str | None = None,
) -> dict[str, Any] | None:
    if not events and not waves:
        return None

    row: dict[str, Any] = {}


    if date is not None:
        row["date"] = date
    if window_start is not None:
        row["window_start"] = window_start
    if window_end is not None:
        row["window_end"] = window_end


    if events:
        t1, _ = wave_kpi.busy_fraction_from_events(events)
        if t1 is not None:
            row["t1"] = t1


    if waves:
        t2_stats = metrics_lib.idle_wave_rates(waves)
        if t2_stats is not None:
            row["t2"] = t2_stats["t2a_rate"]


    if events:
        t3_stats = metrics_lib.concurrency_stats(events)
        if t3_stats is not None:
            row["t3"] = t3_stats["median"]


    if events:
        t4_stats = metrics_lib.model_mix(events)
        if t4_stats is not None:
            row["t4"] = t4_stats["ratio"]


    if events:
        t5_stats = metrics_lib.recovery_reliability(events)
        if t5_stats is not None:
            row["t5"] = t5_stats["ratio"]


    row["t7_holds"] = _compute_t7_holds(events)

    return row


def append_history_row(
    row: dict[str, Any],
    *,
    history_path: Path,
) -> None:
    line = json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
    history_path.parent.mkdir(parents=True, exist_ok=True)
    with open(history_path, "a", encoding="utf-8") as fh:
        fh.write(line)


def _dates_in_events(events: list[dict[str, Any]]) -> list[str]:
    dates: set[str] = set()
    for ev in events:
        ts = _parse_iso(str(ev.get("created_at", "")))
        if ts is not None:
            dates.add(ts.strftime("%Y-%m-%d"))
    return sorted(dates)


def emit_all_days(
    events: list[dict[str, Any]],
    waves: list[dict],
    *,
    history_path: Path,
    drop_counter: DropCounter | None = None,
) -> list[dict[str, Any]]:
    appended: list[dict[str, Any]] = []
    for date_str in _dates_in_events(events):
        start_str = f"{date_str}T00:00:00Z"
        end_str = f"{date_str}T23:59:59Z"
        start_dt = _parse_iso(start_str)
        end_dt = _parse_iso(end_str)
        day_events = filter_events_by_window(events, start_dt, end_dt, drop_counter=drop_counter)
        day_waves = filter_waves_by_date(waves, date_str)
        row = compute_window_row(
            day_events,
            day_waves,
            date=date_str,
            window_start=start_str,
            window_end=end_str,
        )
        if row is not None:
            append_history_row(row, history_path=history_path)
            appended.append(row)
    return appended


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Append a window's T1-T5+T7 row to board/.metrics-history.jsonl.",
    )
    ap.add_argument(
        "--events",
        type=Path,
        default=DEFAULT_EVENTS_PATH,
        help="Path to the DGO-X event store (default: board/.events.jsonl).",
    )
    ap.add_argument(
        "--wave-log",
        type=Path,
        default=DEFAULT_WAVE_LOG_PATH,
        help="Path to the wave log (default: board/.wave-log).",
    )
    ap.add_argument(
        "--history",
        type=Path,
        default=DEFAULT_HISTORY_PATH,
        help="Output JSONL file (default: board/.metrics-history.jsonl).",
    )
    ap.add_argument(
        "--date",
        type=str,
        default=None,
        help="Calendar date YYYY-MM-DD; processes that day (00:00:00Z–23:59:59Z).",
    )
    ap.add_argument(
        "--start",
        type=str,
        default=None,
        help="Window start, YYYY-MM-DDTHH:MM:SSZ (overrides --date start).",
    )
    ap.add_argument(
        "--end",
        type=str,
        default=None,
        help="Window end, YYYY-MM-DDTHH:MM:SSZ (overrides --date end).",
    )
    ap.add_argument(
        "--all",
        dest="all_days",
        action="store_true",
        help="Scan the full event store and emit one row per calendar day (oldest → newest).",
    )
    args = ap.parse_args(argv)


    all_events = wave_kpi.read_events(str(args.events))
    all_waves = metrics_lib.read_waves(str(args.wave_log))


    if args.all_days:
        drop_counter = DropCounter()
        rows = emit_all_days(
            all_events, all_waves, history_path=args.history, drop_counter=drop_counter
        )
        print(f"Appended {len(rows)} day row(s) to {args.history}")
        if drop_counter.count:
            print(
                f"NOTE: {drop_counter.count} event(s) excluded across all windows for a "
                f"missing/non-conforming created_at (DAS-1633) — see "
                f"dgox.created_at.CREATED_AT_FORMAT for the required shape."
            )
        return 0


    date_str: str | None = args.date
    start_str: str | None = args.start
    end_str: str | None = args.end

    if date_str and start_str is None:
        start_str = f"{date_str}T00:00:00Z"
    if date_str and end_str is None:
        end_str = f"{date_str}T23:59:59Z"


    start_dt: datetime | None = None
    end_dt: datetime | None = None

    if start_str is not None:
        start_dt = _parse_iso(start_str)
        if start_dt is None:
            print(
                f"ERROR: --start {start_str!r} is not a valid YYYY-MM-DDTHH:MM:SSZ timestamp.",
                file=sys.stderr,
            )
            return 1

    if end_str is not None:
        end_dt = _parse_iso(end_str)
        if end_dt is None:
            print(
                f"ERROR: --end {end_str!r} is not a valid YYYY-MM-DDTHH:MM:SSZ timestamp.",
                file=sys.stderr,
            )
            return 1


    drop_counter = DropCounter()
    window_events = filter_events_by_window(all_events, start_dt, end_dt, drop_counter=drop_counter)
    window_waves = (
        filter_waves_by_date(all_waves, date_str)
        if date_str
        else all_waves
    )

    row = compute_window_row(
        window_events,
        window_waves,
        date=date_str,
        window_start=start_str,
        window_end=end_str,
    )

    if row is None:
        print("No events or waves in the given window — nothing appended.")
        return 0

    append_history_row(row, history_path=args.history)
    print(f"Appended 1 row to {args.history}: {json.dumps(row, separators=(',', ':'))}")
    if drop_counter.count:
        print(
            f"NOTE: {drop_counter.count} event(s) excluded from this window for a "
            f"missing/non-conforming created_at (DAS-1633) — see "
            f"dgox.created_at.CREATED_AT_FORMAT for the required shape."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
