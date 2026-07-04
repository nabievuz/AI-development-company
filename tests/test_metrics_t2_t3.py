#!/usr/bin/env python3
"""tests/test_metrics_t2_t3.py — T2 idle-wave split + T3 concurrency (R-1 / ADR-002)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import check_concurrency as cc  # noqa: E402  (import after path manipulation)
import check_idle_waves as ciw  # noqa: E402
import metrics_lib as ml  # noqa: E402

T = "2026-06-21T10:%02d:00Z"


def _wave(dispatched: int = 0, nothing: bool = False) -> dict:
    return {
        "disp": ["sonnet"] * dispatched,
        "txt": (["nothing actionable — 2026-06-21 10:00:01"] if nothing else ["| DAS-1 blocked |"]),
    }


def _ev(event_type: str, run_id: str, minute: int) -> dict:
    return {"event_type": event_type, "ticket_id": "DAS-1382", "run_id": run_id, "created_at": T % minute}


def _events_file(tmp_path: Path, events: list[dict]) -> Path:
    p = tmp_path / ".events.jsonl"
    p.write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
    return p


# --------------------------------------------------------------------------- #
# T2 idle-wave split
# --------------------------------------------------------------------------- #

def test_idle_split_none_when_no_waves():
    assert ml.idle_wave_rates([]) is None


def test_idle_split_counts_t2a_and_t2b():
    waves = [
        _wave(dispatched=2),                 # active
        _wave(nothing=True),                 # T2a idle
        _wave(nothing=True),                 # T2a idle
        _wave(nothing=False),                # T2b blocked (no dispatch, not "nothing actionable")
    ]
    r = ml.idle_wave_rates(waves)
    assert r["total"] == 4
    assert r["t2a_idle"] == 2
    assert r["t2b_blocked"] == 1
    assert r["t2a_rate"] == 0.5


def test_idle_cli_inert_without_log(tmp_path):
    assert ciw.main(["--wave-log", str(tmp_path / "nope.wave-log")]) == 0


def test_idle_cli_below_target_exit_0(tmp_path, monkeypatch):
    # 1 idle of 10 waves -> 0.10 <= 0.15
    waves = [_wave(dispatched=1) for _ in range(9)] + [_wave(nothing=True)]
    monkeypatch.setattr(ml, "read_waves", lambda *_: waves)
    assert ciw.main(["--target", "0.15"]) == 0


def test_idle_cli_above_target_exit_1(tmp_path, monkeypatch):
    # 5 idle of 10 -> 0.50 > 0.15
    waves = [_wave(dispatched=1) for _ in range(5)] + [_wave(nothing=True) for _ in range(5)]
    monkeypatch.setattr(ml, "read_waves", lambda *_: waves)
    assert ciw.main(["--target", "0.15"]) == 1


def test_blocked_waves_do_not_fail_the_gate(monkeypatch):
    # all non-active waves are BLOCKED (T2b), not idle (T2a) -> gate passes
    waves = [_wave(dispatched=1)] + [_wave(nothing=False) for _ in range(9)]
    monkeypatch.setattr(ml, "read_waves", lambda *_: waves)
    assert ciw.main(["--target", "0.15"]) == 0


# --------------------------------------------------------------------------- #
# T3 concurrency
# --------------------------------------------------------------------------- #

def test_concurrency_none_when_no_runs():
    assert ml.concurrency_stats([]) is None


def test_concurrency_three_overlapping_runs():
    # r1 [00,10], r2 [02,08], r3 [04,06] all overlap at their starts
    evs = [
        _ev("run_start", "r1", 0), _ev("run_end", "r1", 10),
        _ev("run_start", "r2", 2), _ev("run_end", "r2", 8),
        _ev("run_start", "r3", 4), _ev("run_end", "r3", 6),
    ]
    stats = ml.concurrency_stats(evs)
    # concurrency at starts: r1->1, r2->2, r3->3  => median 2, p95 ~3
    assert stats["samples"] == 3
    assert stats["median"] == 2.0
    assert stats["p95"] >= 2.9


def test_concurrency_cli_inert_without_events(tmp_path):
    assert cc.main(["--events", str(tmp_path / "nope.jsonl")]) == 0


def test_concurrency_cli_below_target_exit_1(tmp_path):
    evs = [_ev("run_start", "r1", 0), _ev("run_end", "r1", 5)]  # median concurrency 1 < 6
    p = _events_file(tmp_path, evs)
    assert cc.main(["--events", str(p), "--target", "6"]) == 1


def test_concurrency_cli_meets_target_exit_0(tmp_path):
    # six runs all active at the same instant -> median 6
    evs = []
    for i in range(6):
        evs += [_ev("run_start", f"r{i}", 0), _ev("run_end", f"r{i}", 10)]
    p = _events_file(tmp_path, evs)
    assert cc.main(["--events", str(p), "--target", "6"]) == 0


def test_zero_length_runs_count_themselves():
    # sub-second runs collapse to start==end at second resolution; 7 concurrent
    # zero-length runs must report concurrency 7, not 0 (review-found T3 bug)
    evs = []
    for i in range(7):
        evs += [_ev("run_start", f"r{i}", 5), _ev("run_end", f"r{i}", 5)]
    stats = ml.concurrency_stats(evs)
    assert stats["median"] == 7.0 and stats["samples"] == 7


def test_zero_length_runs_among_long_runs():
    # 6 sub-second runs at minute 2 concurrent with 2 long runs spanning it -> 8
    evs = [_ev("run_start", "L1", 0), _ev("run_end", "L1", 10),
           _ev("run_start", "L2", 0), _ev("run_end", "L2", 10)]
    for i in range(6):
        evs += [_ev("run_start", f"s{i}", 2), _ev("run_end", f"s{i}", 2)]
    stats = ml.concurrency_stats(evs)
    assert stats["p95"] == 8.0
