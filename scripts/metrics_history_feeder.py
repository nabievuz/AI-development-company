#!/usr/bin/env python3
"""metrics_history_feeder.py — Board metrics-history JSONL feeder (ORGANISM WS4 / DAS-1476).

Reads real span/run events from the DGO-X event store (``board/.events.jsonl``)
and the wave log (``board/.wave-log``), computes T1-T5 + T7_holds for a
date/window, and appends one row to ``board/.metrics-history.jsonl`` —
the file ``loop_controller.py`` reads to count consecutive clean live days for
GATE-6 promotion eligibility.

Row schema (must match ``loop_controller.day_is_clean`` exactly):
  t1          (float)  busy fraction; clean >= 0.60
  t2          (float)  idle-wave rate (t2a); clean <= 0.15
  t3          (float)  effective concurrency (median); clean >= 6
  t4          (float)  low-cost model share; clean >= 0.25
  t5          (float)  recovery reliability; clean >= 0.99
  t7_holds    (bool)   gaming-violations clean; clean = True
  date        (str)    YYYY-MM-DD provenance field (loop_controller ignores)
  window_start (str)   YYYY-MM-DDTHH:MM:SSZ  (loop_controller ignores)
  window_end   (str)   YYYY-MM-DDTHH:MM:SSZ  (loop_controller ignores)

Design invariants (mirror dispatch_emitter.py):
- **Pure core.** ``compute_window_row`` / filter helpers are pure functions of
  their inputs — no clock reads, no network, no filesystem access in the core
  path.  Caller-supplied events/waves make the function deterministically testable.
- **Append-only.** ``append_history_row`` uses ``open(..., "a")`` exclusively and
  never truncates or rewrites existing content.
- **Reuse, never re-implement.** All T-value computations delegate to
  ``wave_kpi`` / ``metrics_lib`` — no reimplementation of event parsing, interval
  pairing, or percentile math.
- **Does NOT modify** ``loop_controller.py`` / ``wave_kpi.py`` / ``metrics_lib.py``.
- **Operator-tempo reader (ADR-0025).** This module reads the event store but
  does NOT affect normal dispatch — it is an out-of-band analytics feeder.

T-value computation sources:
  T1 <- wave_kpi.busy_fraction_from_events(events)[0]
  T2 <- metrics_lib.idle_wave_rates(waves)["t2a_rate"]
  T3 <- metrics_lib.concurrency_stats(events)["median"]
  T4 <- metrics_lib.model_mix(events)["ratio"]
  T5 <- metrics_lib.recovery_reliability(events)["ratio"]
  T7_holds <- metrics_lib.gaming_violations(events): no violations = True

Missing values (None from the library) are NOT written to the row so that
``loop_controller.day_is_clean`` falls back to its below-target defaults
(the day is not clean).  A missing metric is never coerced to a passing value.

Usage:
    # One calendar day:
    python3 scripts/metrics_history_feeder.py --date 2026-07-01

    # Explicit window:
    python3 scripts/metrics_history_feeder.py \\
        --start 2026-07-01T00:00:00Z --end 2026-07-01T23:59:59Z

    # Scan the whole event store, emit oldest->newest (one row per calendar day):
    python3 scripts/metrics_history_feeder.py --all
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Self-locating import — make scripts/ importable regardless of invocation.
# ---------------------------------------------------------------------------

_SCRIPTS_DIR = Path(__file__).resolve().parent  # scripts/
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import metrics_lib  # noqa: E402
import wave_kpi  # noqa: E402
from _paths import ROOT  # noqa: E402
from dgox.created_at import DropCounter, parse_created_at  # noqa: E402

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

# ---------------------------------------------------------------------------
# Internal timestamp helper (mirrors wave_kpi._parse_iso / metrics_lib._parse_iso)
# ---------------------------------------------------------------------------


def _parse_iso(ts: str) -> datetime | None:
    """Parse a ``created_at`` timestamp against the shared write-seam contract.

    DAS-1633: delegates to ``dgox.created_at.parse_created_at`` (the single
    source of truth shared with ``cost_ledger``/``wave_kpi``/``metrics_lib``/
    ``trends``) instead of a locally re-implemented ``strptime``.
    """
    return parse_created_at(ts)


# ---------------------------------------------------------------------------
# Pure filter helpers — no clock reads
# ---------------------------------------------------------------------------


def filter_events_by_window(
    events: list[dict[str, Any]],
    start: datetime | None,
    end: datetime | None,
    *,
    drop_counter: DropCounter | None = None,
) -> list[dict[str, Any]]:
    """Return events whose ``created_at`` falls in [start, end] (inclusive).

    An event with a missing or unparseable ``created_at`` is excluded — this
    exclusion semantics is UNCHANGED and deliberate (DAS-1618: counting
    undated events would make them count in every window forever). What
    changed (DAS-1633) is that the exclusion is no longer silent: pass a
    ``DropCounter`` and it is bumped once per excluded record, so a caller can
    observe how many events the clean-day evidence window just lost instead of
    a smaller number reporting with silent confidence.
    When both ``start`` and ``end`` are None the full list is returned unchanged
    (no filtering happens, so nothing is dropped and the counter is untouched).

    Args:
        events:       The full list of event dicts to filter.
        start:        Window start (inclusive); None means no lower bound.
        end:          Window end   (inclusive); None means no upper bound.
        drop_counter: Optional ``DropCounter`` bumped once per record excluded
                      for a missing/unparseable ``created_at``.

    Returns:
        A new list containing only the events within the window.
    """
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
    """Return waves whose ``date`` field equals ``date_str`` (YYYY-MM-DD).

    ``wave_kpi.parse`` populates ``wave['date']`` from the wave header
    (``===== wave YYYY-MM-DD HH:MM:SS =====``), so this is a direct string match.

    Args:
        waves:    Wave dicts from ``wave_kpi.parse()``.
        date_str: Calendar date string in YYYY-MM-DD format.

    Returns:
        Waves whose ``date`` field matches ``date_str``.
    """
    return [w for w in waves if w.get("date") == date_str]


# ---------------------------------------------------------------------------
# T7_holds derivation — evidence-only, never fabricated
# ---------------------------------------------------------------------------


def _compute_t7_holds(events: list[dict[str, Any]]) -> bool:
    """T7_holds = True when all completions pass R-9 (no gaming violations).

    Uses ``metrics_lib.gaming_violations`` to check that every completion event
    carried a merged PR, green CI, and a T7 pass flag.  Returns False when:
    - There are no completions (``gaming_violations`` returns None).
    - Any completion is missing one or more R-9 evidence fields.

    Never fabricates a pass — the absence of violations in a non-empty
    completion set is the only positive evidence accepted.
    """
    violations = metrics_lib.gaming_violations(events)
    if violations is None:
        # No completions at all — cannot confirm T7 without evidence.
        return False
    return len(violations["violations"]) == 0


# ---------------------------------------------------------------------------
# Pure core — compute one metrics-history row for a window
# ---------------------------------------------------------------------------


def compute_window_row(
    events: list[dict[str, Any]],
    waves: list[dict],
    *,
    date: str | None = None,
    window_start: str | None = None,
    window_end: str | None = None,
) -> dict[str, Any] | None:
    """Compute one metrics-history row for a window's events and waves.

    Pure function — no clock reads, no filesystem access.  All inputs are
    caller-supplied so the function is deterministically unit-testable.

    Returns None when both ``events`` and ``waves`` are empty (an empty window
    carries no evidence and must not emit a row that could inflate the streak).

    T-values are computed from real data via ``wave_kpi`` and ``metrics_lib``.
    A value that those libraries return as None (insufficient data) is NOT
    written to the row, so ``loop_controller.day_is_clean`` falls back to its
    below-target defaults:
      - t1 missing → default -1 → fails >= 0.60
      - t2 missing → default 1  → fails <= 0.15
      - t3 missing → default -1 → fails >= 6
      - t4 missing → default -1 → fails >= 0.25
      - t5 missing → default -1 → fails >= 0.99
      - t7_holds missing/False  → fails bool() check

    Provenance fields (``date``, ``window_start``, ``window_end``) are written
    as extra keys; ``loop_controller`` ignores unknown keys so they are safe.

    Args:
        events:       Span/run events from ``wave_kpi.read_events()`` for the window.
        waves:        Wave dicts from ``wave_kpi.parse()`` for the window.
        date:         Optional YYYY-MM-DD provenance label for the row.
        window_start: Optional YYYY-MM-DDTHH:MM:SSZ window bound (provenance).
        window_end:   Optional YYYY-MM-DDTHH:MM:SSZ window bound (provenance).

    Returns:
        A dict ready to append to ``board/.metrics-history.jsonl``, or None if
        the window is completely empty.
    """
    if not events and not waves:
        return None

    row: dict[str, Any] = {}

    # Provenance — loop_controller ignores these but they aid debugging.
    if date is not None:
        row["date"] = date
    if window_start is not None:
        row["window_start"] = window_start
    if window_end is not None:
        row["window_end"] = window_end

    # T1 — busy fraction (wave_kpi.busy_fraction_from_events).
    # Returns (None, stats) when no paired runs or zero span — carry None through.
    if events:
        t1, _ = wave_kpi.busy_fraction_from_events(events)
        if t1 is not None:
            row["t1"] = t1

    # T2 — idle-wave rate, t2a component (scheduling waste, not blocked waves).
    # Returns None when no waves have been logged.
    if waves:
        t2_stats = metrics_lib.idle_wave_rates(waves)
        if t2_stats is not None:
            row["t2"] = t2_stats["t2a_rate"]

    # T3 — effective concurrency (median concurrent runs sampled at run_start).
    # Returns None when there are no paired run events.
    if events:
        t3_stats = metrics_lib.concurrency_stats(events)
        if t3_stats is not None:
            row["t3"] = t3_stats["median"]

    # T4 — low-cost model share of successful completions.
    # Returns None when no successful completion carries a model field.
    if events:
        t4_stats = metrics_lib.model_mix(events)
        if t4_stats is not None:
            row["t4"] = t4_stats["ratio"]

    # T5 — recovery reliability (successful replays / recovery drills).
    # Returns None when no recovery drills have run.
    if events:
        t5_stats = metrics_lib.recovery_reliability(events)
        if t5_stats is not None:
            row["t5"] = t5_stats["ratio"]

    # T7_holds — R-9 gaming-violations clean (False when no completions).
    # This is always written (False is the safe default when evidence is absent).
    row["t7_holds"] = _compute_t7_holds(events)

    return row


# ---------------------------------------------------------------------------
# Emit helper — append-only JSONL writer
# ---------------------------------------------------------------------------


def append_history_row(
    row: dict[str, Any],
    *,
    history_path: Path,
) -> None:
    """Append one row to the metrics-history JSONL file (append-only).

    Never truncates or rewrites existing content — follows the same
    append-only discipline as ``board/.events.jsonl`` and ``board/.wave-log``.
    The parent directory is created on first use (``board/`` exists in practice;
    the guard is for tests using tmp_path).

    Args:
        row:          The metrics row dict to serialise and append.
        history_path: Absolute path to the ``.metrics-history.jsonl`` file.
    """
    line = json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
    history_path.parent.mkdir(parents=True, exist_ok=True)
    with open(history_path, "a", encoding="utf-8") as fh:
        fh.write(line)


# ---------------------------------------------------------------------------
# Calendar-day scanner — emit one row per day, oldest → newest
# ---------------------------------------------------------------------------


def _dates_in_events(events: list[dict[str, Any]]) -> list[str]:
    """Sorted unique calendar dates (YYYY-MM-DD) found in event ``created_at`` fields."""
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
    """Emit one row per calendar day found in ``events``, oldest → newest.

    Scans the full event list for distinct calendar dates, then for each date
    filters events and waves to that day's window and calls ``compute_window_row``
    + ``append_history_row``.  Rows are appended in chronological (oldest first)
    order as required by ``loop_controller.clean_live_days``, which counts the
    trailing (newest) streak.

    Note: this function does NOT check for existing rows — callers should
    ensure the history file is empty or truncated before a full rescan to avoid
    duplicates.

    Args:
        events:       All events from the full event store (unfiltered).
        waves:        All waves from the wave log (unfiltered).
        history_path: Path to the ``board/.metrics-history.jsonl`` output file.
        drop_counter: Optional ``DropCounter`` (DAS-1633) bumped once per event
                      excluded from a day's window for a missing/unparseable
                      ``created_at`` — accumulates across every day scanned.

    Returns:
        The list of row dicts that were appended (useful for testing/logging).
    """
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


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """CLI entry point.

    Appends one (or many) metrics-history row(s) to board/.metrics-history.jsonl.
    The feeder is an operator-tempo tool — it does not affect /daslab-cycle
    dispatch and may be run between cycles to update the streak evidence.

    Exit codes: 0 (success or nothing-to-do), 1 (bad argument).
    """
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

    # Load raw data from the live stores.
    all_events = wave_kpi.read_events(str(args.events))
    all_waves = metrics_lib.read_waves(str(args.wave_log))

    # --all: scan every calendar day in the event store.
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

    # Resolve window bounds — --date provides shorthand for a full calendar day.
    date_str: str | None = args.date
    start_str: str | None = args.start
    end_str: str | None = args.end

    if date_str and start_str is None:
        start_str = f"{date_str}T00:00:00Z"
    if date_str and end_str is None:
        end_str = f"{date_str}T23:59:59Z"

    # Validate provided timestamps.
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

    # Filter to the window (or use the full event/wave set if no bounds given).
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
