#!/usr/bin/env python3
"""tests/test_check_busy_fraction.py — T1 busy-fraction gate (R-1 / ADR-002).

Proves the union-interval math, the inert (unmeasured) path when there is no
live data, and the >=0.60 threshold enforcement on synthetic run events.
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import check_busy_fraction as cbf  # noqa: E402  (import after path manipulation)
import wave_kpi  # noqa: E402

T = "2026-06-21T10:%02d:00Z"  # minute-parameterised ISO timestamps


def _ev(event_type: str, run_id: str, ts: str, model: str | None = None) -> dict:
    e = {"event_type": event_type, "ticket_id": "DAS-1382", "run_id": run_id, "created_at": ts}
    if model:
        e["model"] = model
    return e


def _write(tmp_path: Path, events: list[dict]) -> Path:
    p = tmp_path / ".events.jsonl"
    p.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")
    return p


def _mk(minute: int) -> dt.datetime:
    return dt.datetime(2026, 6, 21, 10, minute, 0)


# --------------------------------------------------------------------------- #
# Union-interval math
# --------------------------------------------------------------------------- #

def test_union_disjoint():
    # [0,4] + [5,10] = 4m + 5m = 540s
    assert wave_kpi._union_seconds([(_mk(0), _mk(4)), (_mk(5), _mk(10))]) == 540.0


def test_union_overlap_not_double_counted():
    # [0,6] overlaps [4,10] -> union [0,10] = 600s
    assert wave_kpi._union_seconds([(_mk(0), _mk(6)), (_mk(4), _mk(10))]) == 600.0


# --------------------------------------------------------------------------- #
# busy_fraction_from_events
# --------------------------------------------------------------------------- #

def test_none_when_empty():
    frac, stats = wave_kpi.busy_fraction_from_events([])
    assert frac is None
    assert stats["events"] == 0


def test_none_when_no_completed_runs():
    frac, stats = wave_kpi.busy_fraction_from_events([_ev("run_start", "r1", T % 0)])
    assert frac is None
    assert stats["runs_started"] == 1
    assert stats["runs_completed"] == 0


def test_fraction_computed():
    # span 0:00..0:10 = 600s; active [0:00-0:04] + [0:05-0:10] = 540s -> 0.90
    # model lives on run_end (the completion; ADR-0023 §4), never run_start.
    evs = [
        _ev("run_start", "r1", T % 0),
        _ev("run_end", "r1", T % 4),
        _ev("run_start", "r2", T % 5),
        _ev("run_end", "r2", T % 10, model="sonnet"),
    ]
    frac, stats = wave_kpi.busy_fraction_from_events(evs)
    assert frac == pytest.approx(0.90)
    assert stats["runs_completed"] == 2
    assert stats["model_mix"]["sonnet"] == 1


# --------------------------------------------------------------------------- #
# CLI / exit codes
# --------------------------------------------------------------------------- #

def test_cli_missing_store_is_inert_exit_0(tmp_path):
    assert cbf.main(["--events", str(tmp_path / "nope.jsonl")]) == 0


def test_cli_unmeasured_exit_0(tmp_path):
    p = _write(tmp_path, [_ev("run_start", "r1", T % 0)])
    assert cbf.main(["--events", str(p)]) == 0


def test_cli_above_target_exit_0(tmp_path):
    evs = [
        _ev("run_start", "r1", T % 0),
        _ev("run_end", "r1", T % 4),
        _ev("run_start", "r2", T % 5),
        _ev("run_end", "r2", T % 10),
    ]  # 0.90 >= 0.60
    p = _write(tmp_path, evs)
    assert cbf.main(["--events", str(p), "--target", "0.60"]) == 0


def test_cli_below_target_exit_1(tmp_path):
    # active [0:00-0:02] = 120s; span 0:00..0:10 = 600s -> 0.20 < 0.60
    evs = [
        _ev("run_start", "r1", T % 0),
        _ev("run_end", "r1", T % 2),
        _ev("run_start", "r2", T % 10),  # start only: extends span, no interval
    ]
    p = _write(tmp_path, evs)
    assert cbf.main(["--events", str(p), "--target", "0.60"]) == 1
