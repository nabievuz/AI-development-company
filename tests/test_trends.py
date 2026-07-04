#!/usr/bin/env python3
"""tests/test_trends.py — Historical Trend Views (R20 / RFC-003)."""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import trends as tr  # noqa: E402  (import after path manipulation)


def _ends(minutes: list[int]) -> list[dict]:
    return [{"event_type": "run_end", "run_id": f"r{i}",
             "created_at": f"2026-06-21T10:{m:02d}:00Z"} for i, m in enumerate(minutes)]


def test_classify_improving():
    assert tr.classify_trend([1, 2, 3, 4, 5], higher_is_better=True)["direction"] == "improving"


def test_classify_degrading():
    assert tr.classify_trend([5, 4, 3, 2, 1], higher_is_better=True)["direction"] == "degrading"


def test_classify_flat():
    assert tr.classify_trend([3, 3, 3, 3], higher_is_better=True)["direction"] == "flat"


def test_classify_insufficient():
    assert tr.classify_trend([7])["direction"] == "insufficient"
    assert tr.classify_trend([])["direction"] == "insufficient"


def test_nan_does_not_fabricate_a_trend():
    nan = float("nan")
    assert tr.classify_trend([nan, 1, 2])["direction"] in ("insufficient", "flat", "improving")
    assert tr.classify_trend([nan, nan])["direction"] == "insufficient"
    assert tr.classify_trend([float("inf"), 1])["direction"] == "insufficient"


def test_higher_is_better_flips_meaning():
    # for a 'lower is better' metric, a rising series is degrading
    assert tr.classify_trend([1, 2, 3], higher_is_better=False)["direction"] == "degrading"


def test_throughput_series_buckets():
    # 5 runs across a 40-minute span into 5 windows
    series = tr.throughput_series(_ends([0, 10, 20, 30, 40]), n_windows=5)
    assert len(series) == 5
    assert sum(series) == 5.0


def test_throughput_series_insufficient():
    assert tr.throughput_series(_ends([0, 10]), n_windows=5) == []


def test_cli_inert(tmp_path):
    assert tr.main(["--events", str(tmp_path / "nope.jsonl")]) == 0


def test_cli_real_run_exit_0():
    assert tr.main([]) == 0
