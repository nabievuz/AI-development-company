#!/usr/bin/env python3

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

import check_busy_fraction as cbf
import wave_kpi

T = "2026-06-21T10:%02d:00Z"


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


def test_union_disjoint():

    assert wave_kpi._union_seconds([(_mk(0), _mk(4)), (_mk(5), _mk(10))]) == 540.0


def test_union_overlap_not_double_counted():

    assert wave_kpi._union_seconds([(_mk(0), _mk(6)), (_mk(4), _mk(10))]) == 600.0


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
    ]
    p = _write(tmp_path, evs)
    assert cbf.main(["--events", str(p), "--target", "0.60"]) == 0


def test_cli_below_target_exit_1(tmp_path):

    evs = [
        _ev("run_start", "r1", T % 0),
        _ev("run_end", "r1", T % 2),
        _ev("run_start", "r2", T % 10),
    ]
    p = _write(tmp_path, evs)
    assert cbf.main(["--events", str(p), "--target", "0.60"]) == 1


def test_an_event_outside_the_run_lifecycle_does_not_stretch_the_window(tmp_path):
    paired = [_ev("run_start", "r1", T % 0), _ev("run_end", "r1", T % 10)]
    alone = dict(paired[0])
    alone.update(event_type="agent_invocation", run_id="r1", created_at=T % 3600)

    before, _ = wave_kpi.busy_fraction_from_events(paired)
    after, _ = wave_kpi.busy_fraction_from_events([*paired, alone])

    assert before == after == 1.0


def test_an_unfinished_run_still_counts_as_elapsed_time(tmp_path):
    evs = [
        _ev("run_start", "r1", T % 0),
        _ev("run_end", "r1", T % 2),
        _ev("run_start", "r2", T % 10),
    ]
    fraction, _ = wave_kpi.busy_fraction_from_events(evs)
    assert fraction == 0.2
