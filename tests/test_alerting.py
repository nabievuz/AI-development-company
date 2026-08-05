#!/usr/bin/env python3

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import alerting as al

TH = {"t1_busy_min": 0.60, "memory_health_min": 0.80}


def test_no_alerts_when_inert():

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


def _cli(tmp_path, events_lines: list[str] | None = None) -> int:
    events = tmp_path / "e.jsonl"
    events.write_text("\n".join(events_lines or []), encoding="utf-8")
    return al.main([
        "--events", str(events),
        "--memory-store", str(tmp_path / "m.jsonl"),
        "--memory-config", str(REPO_ROOT / "config" / "memory_governance.yaml"),
        "--thresholds", str(REPO_ROOT / "config" / "alert_thresholds.yaml"),
    ])


def test_cli_empty_stores_report_no_data_not_nominal(tmp_path):
    rc = al.main([
        "--events", str(tmp_path / "e.jsonl"),
        "--memory-store", str(tmp_path / "m.jsonl"),
        "--memory-config", str(REPO_ROOT / "config" / "memory_governance.yaml"),
        "--thresholds", str(REPO_ROOT / "config" / "alert_thresholds.yaml"),
    ])
    assert rc == al.CliExit.NO_DATA
    assert rc != al.CliExit.HEALTHY


def test_cli_healthy_with_data(tmp_path):
    quiet_event = json.dumps({
        "event_type": "run_end", "run_id": "R1", "outcome": "success",
        "created_at": "2026-07-04T10:10:00Z", "model": "sonnet",
    })
    assert _cli(tmp_path, [quiet_event]) == al.CliExit.HEALTHY


def test_cli_degraded_when_an_anomaly_fires(tmp_path, monkeypatch):
    monkeypatch.setattr(al, "evaluate_alerts",
                        lambda *a, **k: [{"severity": "critical", "metric": "T7", "message": "m"}])
    event = json.dumps({"event_type": "run_start", "run_id": "R1",
                        "created_at": "2026-07-04T10:00:00Z"})
    assert _cli(tmp_path, [event]) == al.CliExit.DEGRADED


def test_cli_exit_codes_are_distinct():
    codes = {al.CliExit.HEALTHY, al.CliExit.DEGRADED, al.CliExit.USAGE, al.CliExit.NO_DATA}
    assert len(codes) == 4


def test_observability_data_points_counts_both_stores(tmp_path):
    events = tmp_path / "e.jsonl"
    events.write_text(json.dumps({"event_type": "run_start"}) + "\n")
    memory = tmp_path / "m.jsonl"
    memory.write_text(json.dumps({"id": "m1"}) + "\n")
    assert al.observability_data_points(events, memory) == 2
    assert al.observability_data_points(tmp_path / "absent.jsonl", tmp_path / "absent2.jsonl") == 0
