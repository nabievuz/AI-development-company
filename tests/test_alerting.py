#!/usr/bin/env python3
"""tests/test_alerting.py — threshold alerting + Quiet Mode (R21 / RFC-003)."""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import alerting as al  # noqa: E402  (import after path manipulation)

TH = {"t1_busy_min": 0.60, "memory_health_min": 0.80}


def test_no_alerts_when_inert():
    # all readings absent (no live data) -> no alerts
    assert al.evaluate_alerts({"t1_busy_fraction": None, "memory_health": None, "break_glass_active": False}, TH) == []


def test_t1_below_target_warns():
    alerts = al.evaluate_alerts({"t1_busy_fraction": 0.40}, TH)
    assert any(a["metric"] == "T1" and a["severity"] == "warning" for a in alerts)


def test_t1_at_target_no_alert():
    assert al.evaluate_alerts({"t1_busy_fraction": 0.60}, TH) == []


def test_critical_alerts():
    for reading in ({"t7_regressed": True}, {"break_glass_active": True}, {"never_auto_violations": 2}):
        alerts = al.evaluate_alerts(reading, TH)
        assert alerts and alerts[0]["severity"] == "critical"


def test_memory_health_low_warns():
    assert any(a["metric"] == "memory" for a in al.evaluate_alerts({"memory_health": 0.5}, TH))


def test_sorted_critical_first():
    alerts = al.evaluate_alerts({"t1_busy_fraction": 0.4, "break_glass_active": True}, TH)
    assert alerts[0]["severity"] == "critical"


def test_quiet_mode_drops_info():
    mixed = [{"severity": "info", "metric": "x", "message": "m"},
             {"severity": "warning", "metric": "y", "message": "m"},
             {"severity": "critical", "metric": "z", "message": "m"}]
    assert [a["severity"] for a in al.filter_quiet(mixed)] == ["warning", "critical"]


def test_cli_inert(tmp_path):
    rc = al.main([
        "--events", str(tmp_path / "e.jsonl"),
        "--memory-store", str(tmp_path / "m.jsonl"),
        "--memory-config", str(REPO_ROOT / "config" / "memory_governance.yaml"),
        "--thresholds", str(REPO_ROOT / "config" / "alert_thresholds.yaml"),
    ])
    assert rc == 0


def test_cli_real_run_exit_0():
    assert al.main([]) == 0
