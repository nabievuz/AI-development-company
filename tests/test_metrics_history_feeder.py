#!/usr/bin/env python3
"""tests/test_metrics_history_feeder.py — Unit suite for scripts/metrics_history_feeder.py.

Tests prove:
- compute_window_row produces the correct T1-T5 + T7_holds schema.
- Missing/None metric values are absent from the row (not coerced to a failing value).
- T7_holds is False without completions and True when all R-9 checks pass.
- filter_events_by_window correctly partitions by created_at.
- filter_waves_by_date correctly partitions by date field.
- append_history_row is append-only (never truncates).
- emit_all_days emits rows oldest → newest, one per calendar day.
- loop_controller.clean_live_days correctly computes the consecutive clean-day
  streak against feeder-produced rows:
    - a clean trailing run,
    - a break in the middle,
    - an all-empty history → 0.
- Pure core: compute_window_row is deterministic (no clock reads).
- Gitignore: board/.metrics-history.jsonl is listed in .gitignore.

All tests write to tmp_path — never to board/.metrics-history.jsonl.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS = _REPO_ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import loop_controller as lc  # noqa: E402
import wave_kpi  # noqa: E402
from dispatch_emitter import DispatchRecord, emit_wave  # noqa: E402
from metrics_history_feeder import (  # noqa: E402
    _compute_t7_holds,
    _dates_in_events,
    _parse_iso,
    append_history_row,
    compute_window_row,
    emit_all_days,
    filter_events_by_window,
    filter_waves_by_date,
)

# ---------------------------------------------------------------------------
# Helpers — synthetic events and waves
# ---------------------------------------------------------------------------

_T = lc.DEFAULT_TARGETS  # promotion-readiness targets


def _record(
    *,
    ticket_id: str = "DAS-1476",
    run_id: str = "run-1476",
    start: str = "2026-07-01T00:00:00Z",
    end: str = "2026-07-01T00:05:00Z",
    model: str = "sonnet",
    outcome: str = "success",
    merged_pr: object = "https://github.com/pr/1",
    ci_status: str = "green",
    t7_pass: object = True,
    t7_score: float = 0.95,
) -> DispatchRecord:
    """A well-formed DispatchRecord with sensible defaults."""
    return DispatchRecord(
        ticket_id=ticket_id,
        run_id=run_id,
        goal="organism-ws4-heartbeat",
        engine_version="1.2.0",
        model=model,
        role_key="backend-eng-1",
        start=start,
        end=end,
        outcome=outcome,
        merged_pr=merged_pr,
        ci_status=ci_status,
        t7_pass=t7_pass,
        t7_score=t7_score,
    )


def _make_events(tmp_path: Path, records: list[DispatchRecord]) -> list[dict]:
    """Emit dispatch records to a temp store and return the events."""
    store_path = tmp_path / "events.jsonl"
    emit_wave(records, store_path=store_path)
    return wave_kpi.read_events(str(store_path))


def _clean_day() -> dict:
    """A day dict that passes all day_is_clean targets."""
    return {"t1": 0.70, "t2": 0.10, "t3": 7.0, "t4": 0.30, "t5": 1.0, "t7_holds": True}


def _dirty_day() -> dict:
    """A day dict that fails day_is_clean (low T1, T7 off)."""
    return {"t1": 0.10, "t2": 0.50, "t3": 1.0, "t4": 0.05, "t5": 0.50, "t7_holds": False}


# A synthetic wave with overlapping runs so T3 concurrency > 1 and T4 has data.
def _synthetic_events(tmp_path: Path) -> list[dict]:
    """Four overlapping runs across two models — gives non-None T1, T3, T4."""
    records = [
        _record(
            ticket_id="DAS-4001", run_id="run-4001",
            start="2026-07-01T00:00:00Z", end="2026-07-01T00:06:00Z",
            model="sonnet",
        ),
        _record(
            ticket_id="DAS-4002", run_id="run-4002",
            start="2026-07-01T00:01:00Z", end="2026-07-01T00:07:00Z",
            model="haiku",
        ),
        _record(
            ticket_id="DAS-4003", run_id="run-4003",
            start="2026-07-01T00:02:00Z", end="2026-07-01T00:08:00Z",
            model="sonnet",
        ),
        _record(
            ticket_id="DAS-4004", run_id="run-4004",
            start="2026-07-01T00:03:00Z", end="2026-07-01T00:09:00Z",
            model="haiku",
        ),
    ]
    return _make_events(tmp_path, records)


# ---------------------------------------------------------------------------
# _parse_iso
# ---------------------------------------------------------------------------


def test_parse_iso_valid():
    ts = _parse_iso("2026-07-01T12:30:00Z")
    assert isinstance(ts, datetime)
    assert ts.year == 2026 and ts.month == 7 and ts.day == 1


def test_parse_iso_invalid_returns_none():
    assert _parse_iso("not-a-timestamp") is None
    assert _parse_iso("") is None
    assert _parse_iso(None) is None  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# filter_events_by_window
# ---------------------------------------------------------------------------


def test_filter_events_by_window_basic(tmp_path: Path):
    events = _synthetic_events(tmp_path)
    start = _parse_iso("2026-07-01T00:01:00Z")
    end = _parse_iso("2026-07-01T00:02:00Z")
    result = filter_events_by_window(events, start, end)
    # Only events with created_at in [00:01, 00:02] should be included.
    for ev in result:
        ts = _parse_iso(str(ev.get("created_at", "")))
        assert ts is not None
        assert start <= ts <= end


def test_filter_events_no_bounds_returns_all(tmp_path: Path):
    events = _synthetic_events(tmp_path)
    assert filter_events_by_window(events, None, None) == events


def test_filter_events_empty_window(tmp_path: Path):
    events = _synthetic_events(tmp_path)
    far_future = _parse_iso("2099-01-01T00:00:00Z")
    result = filter_events_by_window(events, far_future, far_future)
    assert result == []


# ---------------------------------------------------------------------------
# filter_waves_by_date
# ---------------------------------------------------------------------------


def test_filter_waves_by_date_matches():
    waves = [{"date": "2026-07-01"}, {"date": "2026-07-02"}, {"date": "2026-07-01"}]
    result = filter_waves_by_date(waves, "2026-07-01")
    assert len(result) == 2
    assert all(w["date"] == "2026-07-01" for w in result)


def test_filter_waves_by_date_no_match():
    waves = [{"date": "2026-07-02"}]
    assert filter_waves_by_date(waves, "2026-07-01") == []


def test_filter_waves_by_date_empty():
    assert filter_waves_by_date([], "2026-07-01") == []


# ---------------------------------------------------------------------------
# _compute_t7_holds
# ---------------------------------------------------------------------------


def test_t7_holds_true_when_all_pass(tmp_path: Path):
    events = _synthetic_events(tmp_path)
    assert _compute_t7_holds(events) is True


def test_t7_holds_false_when_no_events():
    assert _compute_t7_holds([]) is False


def test_t7_holds_false_when_violations_present(tmp_path: Path):
    """A run_end without a merged_pr triggers a gaming violation → T7_holds False."""
    records = [
        _record(
            ticket_id="DAS-5001", run_id="run-5001",
            merged_pr=None,  # missing PR → violation
            t7_pass=True,
            ci_status="green",
        ),
    ]
    events = _make_events(tmp_path, records)
    assert _compute_t7_holds(events) is False


def test_t7_holds_false_when_t7_pass_missing(tmp_path: Path):
    """A run_end without t7_pass → gaming violation → T7_holds False."""
    records = [
        _record(
            ticket_id="DAS-5002", run_id="run-5002",
            t7_pass=False,  # not a T7 pass
            merged_pr="https://github.com/pr/ok",
            ci_status="green",
        ),
    ]
    events = _make_events(tmp_path, records)
    assert _compute_t7_holds(events) is False


# ---------------------------------------------------------------------------
# compute_window_row — schema and values
# ---------------------------------------------------------------------------


def test_compute_window_row_none_when_empty():
    """An empty window produces None (no fabrication)."""
    assert compute_window_row([], []) is None


def test_compute_window_row_has_t7_holds_field(tmp_path: Path):
    events = _synthetic_events(tmp_path)
    row = compute_window_row(events, [], date="2026-07-01")
    assert row is not None
    assert "t7_holds" in row


def test_compute_window_row_t1_is_real_fraction(tmp_path: Path):
    events = _synthetic_events(tmp_path)
    row = compute_window_row(events, [])
    assert row is not None
    t1 = row.get("t1")
    assert t1 is not None, "T1 should be computed from overlapping runs"
    assert 0.0 <= t1 <= 1.0


def test_compute_window_row_t3_median_real(tmp_path: Path):
    events = _synthetic_events(tmp_path)
    row = compute_window_row(events, [])
    assert row is not None
    t3 = row.get("t3")
    assert t3 is not None, "T3 should be computed from paired run events"
    assert t3 > 0


def test_compute_window_row_t4_model_mix_real(tmp_path: Path):
    events = _synthetic_events(tmp_path)
    row = compute_window_row(events, [])
    assert row is not None
    t4 = row.get("t4")
    assert t4 is not None, "T4 should be computed from successful completions"
    # Two out of four completions on haiku → ratio = 0.5
    assert t4 == pytest.approx(0.5)


def test_compute_window_row_t5_none_without_recovery_drills(tmp_path: Path):
    """T5 should be absent when no recovery drills have run (not fabricated as 0)."""
    events = _synthetic_events(tmp_path)
    row = compute_window_row(events, [])
    assert row is not None
    # No recovery_drill events in the synthetic wave → t5 must be absent.
    assert "t5" not in row


def test_compute_window_row_t2_none_without_waves(tmp_path: Path):
    """T2 should be absent when no wave log entries exist (not fabricated)."""
    events = _synthetic_events(tmp_path)
    row = compute_window_row(events, [])  # empty wave list
    assert row is not None
    assert "t2" not in row


def test_compute_window_row_with_waves_has_t2(tmp_path: Path):
    """T2 is present when wave data is supplied."""
    events = _synthetic_events(tmp_path)
    # Fabricate a wave dict matching the shape wave_kpi.parse() produces.
    # A wave with no dispatches and 'nothing actionable' in txt → idle (t2a).
    idle_wave = {
        "date": "2026-07-01",
        "start": datetime(2026, 7, 1, 0, 0, 0),
        "end": datetime(2026, 7, 1, 0, 1, 0),
        "idle_decl": 60,
        "txt": ["nothing actionable — 2026-07-01 00:01:00"],
        "disp": [],
    }
    waves = [idle_wave]
    row = compute_window_row(events, waves, date="2026-07-01")
    assert row is not None
    assert "t2" in row
    assert row["t2"] == 1.0  # 1 idle / 1 total = 100%


def test_compute_window_row_provenance_fields(tmp_path: Path):
    events = _synthetic_events(tmp_path)
    row = compute_window_row(
        events, [],
        date="2026-07-01",
        window_start="2026-07-01T00:00:00Z",
        window_end="2026-07-01T23:59:59Z",
    )
    assert row is not None
    assert row["date"] == "2026-07-01"
    assert row["window_start"] == "2026-07-01T00:00:00Z"
    assert row["window_end"] == "2026-07-01T23:59:59Z"


def test_compute_window_row_is_deterministic(tmp_path: Path):
    """Pure core: same inputs → byte-identical rows (no clock reads)."""
    events = _synthetic_events(tmp_path)
    row_a = compute_window_row(events, [], date="2026-07-01")
    row_b = compute_window_row(events, [], date="2026-07-01")
    assert row_a == row_b


def test_compute_window_row_none_missing_values_not_fabricated():
    """When events carry no paired runs, T1/T3/T4/T5 must be absent (not 0)."""
    # Craft events that have no run_start/run_end pairs.
    events = [
        {"event_type": "routing_decision", "ticket_id": "DAS-9999",
         "created_at": "2026-07-01T12:00:00Z"},
    ]
    row = compute_window_row(events, [])
    assert row is not None
    # T1: no paired runs → None from busy_fraction_from_events → absent in row.
    assert "t1" not in row
    # T3: no paired intervals → None from concurrency_stats → absent in row.
    assert "t3" not in row
    # T4: no successful completions with model → None from model_mix → absent.
    assert "t4" not in row
    # T7_holds: no completions → False (never fabricated True).
    assert row["t7_holds"] is False


# ---------------------------------------------------------------------------
# append_history_row — append-only behaviour
# ---------------------------------------------------------------------------


def test_append_history_row_creates_file(tmp_path: Path):
    path = tmp_path / "hist.jsonl"
    append_history_row({"t1": 0.7, "t7_holds": True}, history_path=path)
    assert path.exists()
    lines = path.read_text().splitlines()
    assert len(lines) == 1
    row = json.loads(lines[0])
    assert row["t1"] == pytest.approx(0.7)
    assert row["t7_holds"] is True


def test_append_history_row_is_append_only(tmp_path: Path):
    path = tmp_path / "hist.jsonl"
    append_history_row({"t1": 0.7, "t7_holds": True}, history_path=path)
    first_text = path.read_text()
    append_history_row({"t1": 0.8, "t7_holds": False}, history_path=path)
    second_text = path.read_text()
    # Original content is still a prefix — nothing was overwritten.
    assert second_text.startswith(first_text)
    lines = second_text.splitlines()
    assert len(lines) == 2


def test_append_history_row_valid_json_lines(tmp_path: Path):
    path = tmp_path / "hist.jsonl"
    rows = [_clean_day(), _dirty_day()]
    for r in rows:
        append_history_row(r, history_path=path)
    for line in path.read_text().splitlines():
        obj = json.loads(line)
        assert isinstance(obj, dict)


# ---------------------------------------------------------------------------
# _dates_in_events
# ---------------------------------------------------------------------------


def test_dates_in_events_sorted_unique():
    events = [
        {"created_at": "2026-07-03T10:00:00Z"},
        {"created_at": "2026-07-01T08:00:00Z"},
        {"created_at": "2026-07-01T22:00:00Z"},
        {"created_at": "2026-07-02T00:00:00Z"},
    ]
    result = _dates_in_events(events)
    assert result == ["2026-07-01", "2026-07-02", "2026-07-03"]


def test_dates_in_events_empty():
    assert _dates_in_events([]) == []


# ---------------------------------------------------------------------------
# emit_all_days — oldest → newest
# ---------------------------------------------------------------------------


def _two_day_events(tmp_path: Path) -> list[dict]:
    """Events spanning two calendar days (2026-07-01 and 2026-07-02)."""
    day1 = [
        _record(
            ticket_id="DAS-6001", run_id="run-6001",
            start="2026-07-01T00:00:00Z", end="2026-07-01T00:05:00Z",
        ),
        _record(
            ticket_id="DAS-6002", run_id="run-6002",
            start="2026-07-01T01:00:00Z", end="2026-07-01T01:05:00Z",
        ),
    ]
    day2 = [
        _record(
            ticket_id="DAS-6003", run_id="run-6003",
            start="2026-07-02T00:00:00Z", end="2026-07-02T00:05:00Z",
        ),
        _record(
            ticket_id="DAS-6004", run_id="run-6004",
            start="2026-07-02T01:00:00Z", end="2026-07-02T01:05:00Z",
        ),
    ]
    return _make_events(tmp_path, day1 + day2)


def test_emit_all_days_emits_two_rows(tmp_path: Path):
    events = _two_day_events(tmp_path)
    hist_path = tmp_path / "hist.jsonl"
    rows = emit_all_days(events, [], history_path=hist_path)
    assert len(rows) == 2
    assert hist_path.read_text().count("\n") == 2


def test_emit_all_days_oldest_first(tmp_path: Path):
    events = _two_day_events(tmp_path)
    hist_path = tmp_path / "hist.jsonl"
    rows = emit_all_days(events, [], history_path=hist_path)
    # Rows should be in chronological order (oldest first).
    dates = [r.get("date") for r in rows]
    assert dates == sorted(dates)
    assert dates[0] == "2026-07-01"
    assert dates[1] == "2026-07-02"


def test_emit_all_days_empty_events(tmp_path: Path):
    hist_path = tmp_path / "hist.jsonl"
    rows = emit_all_days([], [], history_path=hist_path)
    assert rows == []
    assert not hist_path.exists()


# ---------------------------------------------------------------------------
# loop_controller.clean_live_days against feeder-produced rows
# (THE LOAD-BEARING STREAK TESTS — acceptance criteria)
# ---------------------------------------------------------------------------


def test_streak_all_clean_rows():
    """A sequence of 7 clean rows → streak = 7 (clean trailing run)."""
    history = [_clean_day() for _ in range(7)]
    assert lc.clean_live_days(history, _T) == 7


def test_streak_break_in_middle():
    """Clean days, then a dirty day, then two more clean days → streak = 2."""
    history = (
        [_clean_day() for _ in range(5)]
        + [_dirty_day()]
        + [_clean_day() for _ in range(2)]
    )
    assert lc.clean_live_days(history, _T) == 2


def test_streak_all_empty_history():
    """Empty history → streak = 0 (never fabricates readiness)."""
    assert lc.clean_live_days([], _T) == 0


def test_streak_all_dirty():
    """All dirty rows → streak = 0."""
    history = [_dirty_day() for _ in range(5)]
    assert lc.clean_live_days(history, _T) == 0


def test_streak_dirty_then_all_clean():
    """1 dirty day followed by 7 clean days → streak = 7."""
    history = [_dirty_day()] + [_clean_day() for _ in range(7)]
    assert lc.clean_live_days(history, _T) == 7


def test_streak_with_feeder_produced_rows(tmp_path: Path):
    """Feeder-produced rows drive loop_controller.clean_live_days end-to-end.

    Three days of overlapping-run events are emitted via emit_all_days; the
    resulting rows are loaded and fed to clean_live_days.  Since the synthetic
    events satisfy T1/T3/T4 but NOT T3 >= 6 (4 runs → median ~= 2) nor T2,
    day_is_clean returns False for each → streak = 0.
    This proves the end-to-end wiring without inflating the streak.
    """
    hist_path = tmp_path / "hist.jsonl"
    # 3 days × 4 overlapping runs each.
    records: list[DispatchRecord] = []
    for day_n in range(3):
        date = f"2026-07-0{day_n + 1}"
        for i in range(4):
            records.append(
                _record(
                    ticket_id=f"DAS-70{day_n}{i}",
                    run_id=f"run-70{day_n}{i}",
                    start=f"{date}T00:0{i}:00Z",
                    end=f"{date}T00:0{i + 1}:00Z",
                )
            )
    events = _make_events(tmp_path / "events.jsonl", records)  # type: ignore[arg-type]

    # Emit via the feeder — one row per calendar day, oldest → newest.
    emit_all_days(events, [], history_path=hist_path)
    lines = hist_path.read_text().splitlines()
    assert len(lines) == 3  # one row per day

    # Load the produced rows exactly as loop_controller does.
    import loop_controller as lc2
    history = lc2._load_jsonl(hist_path)
    streak = lc2.clean_live_days(history, _T)
    # Synthetic events don't satisfy all targets (T3 < 6, T5 absent) → 0 streak.
    assert streak == 0


def test_streak_with_hand_built_clean_rows_via_append(tmp_path: Path):
    """Hand-built clean rows appended via append_history_row → streak = 7."""
    import loop_controller as lc2

    hist_path = tmp_path / "hist.jsonl"
    for i in range(7):
        row = dict(
            _clean_day(),
            date=f"2026-07-0{i + 1}",
            window_start=f"2026-07-0{i + 1}T00:00:00Z",
            window_end=f"2026-07-0{i + 1}T23:59:59Z",
        )
        append_history_row(row, history_path=hist_path)

    history = lc2._load_jsonl(hist_path)
    assert lc2.clean_live_days(history, _T) == 7


def test_streak_with_mixed_rows_via_append(tmp_path: Path):
    """5 clean, 1 dirty, 2 clean → streak = 2 (break correctly detected)."""
    import loop_controller as lc2

    hist_path = tmp_path / "hist.jsonl"
    days = (
        [_clean_day() for _ in range(5)]
        + [_dirty_day()]
        + [_clean_day() for _ in range(2)]
    )
    for _i, d in enumerate(days):
        append_history_row(d, history_path=hist_path)

    history = lc2._load_jsonl(hist_path)
    assert lc2.clean_live_days(history, _T) == 2


# ---------------------------------------------------------------------------
# Gitignore check — board/.metrics-history.jsonl must be gitignored
# ---------------------------------------------------------------------------


def test_gitignore_lists_metrics_history():
    """board/.metrics-history.jsonl must appear in the repo .gitignore."""
    gitignore_path = _REPO_ROOT / ".gitignore"
    assert gitignore_path.exists(), ".gitignore not found at repo root"
    content = gitignore_path.read_text(encoding="utf-8")
    # Accept any line that contains the file name (with or without path prefix).
    matches = [
        line.strip()
        for line in content.splitlines()
        if ".metrics-history.jsonl" in line and not line.strip().startswith("#")
    ]
    assert matches, (
        "board/.metrics-history.jsonl is not listed in .gitignore — "
        "it must be gitignored (runtime state, never committed)"
    )


# ---------------------------------------------------------------------------
# CLI smoke test
# ---------------------------------------------------------------------------


def test_cli_no_args_prints_nothing_to_do(capsys, tmp_path: Path):
    """With no events, CLI appends nothing and exits 0."""
    from metrics_history_feeder import main

    rc = main([
        "--events", str(tmp_path / "nope.jsonl"),
        "--wave-log", str(tmp_path / "nope.log"),
        "--history", str(tmp_path / "hist.jsonl"),
        "--date", "2026-07-01",
    ])
    assert rc == 0
    captured = capsys.readouterr()
    assert "nothing appended" in captured.out


def test_cli_invalid_start_exits_1(tmp_path: Path):
    """A bad --start argument should exit 1."""
    from metrics_history_feeder import main

    rc = main([
        "--events", str(tmp_path / "nope.jsonl"),
        "--wave-log", str(tmp_path / "nope.log"),
        "--history", str(tmp_path / "hist.jsonl"),
        "--start", "not-a-ts",
    ])
    assert rc == 1


def test_cli_all_mode_no_events(capsys, tmp_path: Path):
    """--all with no events appends 0 rows and exits 0."""
    from metrics_history_feeder import main

    rc = main([
        "--events", str(tmp_path / "nope.jsonl"),
        "--wave-log", str(tmp_path / "nope.log"),
        "--history", str(tmp_path / "hist.jsonl"),
        "--all",
    ])
    assert rc == 0
    assert "0 day row(s)" in capsys.readouterr().out
