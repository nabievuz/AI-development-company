#!/usr/bin/env python3
"""tests/test_alerting_cost.py — cost-breach alerting and budget governor (DAS-1461)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import alerting as al  # noqa: E402

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

# Budget config matching config/budgets.yaml caps section
BUDGETS = {
    "caps": {
        "per_run": {"max_cost_usd": 50.0},
        "per_day": {"max_cost_usd": 500.0},
    }
}
# Warn band = 80% of limit: per_run warn at >=40, breach at >=50
#                           per_day warn at >=400, breach at >=500

TH = {"t1_busy_min": 0.60, "memory_health_min": 0.80}


# ---------------------------------------------------------------------------
# budget_governor — ok / warn / breach bands
# ---------------------------------------------------------------------------


def test_governor_ok_both_dimensions():
    totals = {"per_run_cost_usd": 10.0, "per_day_cost_usd": 50.0}
    result = al.budget_governor(totals, BUDGETS)
    assert result["status"] == "ok"
    assert result["details"] == []


def test_governor_warn_per_run():
    # 82% of $50 = $41 → warn
    totals = {"per_run_cost_usd": 41.0, "per_day_cost_usd": 10.0}
    result = al.budget_governor(totals, BUDGETS)
    assert result["status"] == "warn"
    dims = {d["dimension"] for d in result["details"]}
    assert "per_run" in dims
    assert "per_day" not in dims


def test_governor_warn_per_day():
    # 82% of $500 = $410 → warn
    totals = {"per_run_cost_usd": 5.0, "per_day_cost_usd": 410.0}
    result = al.budget_governor(totals, BUDGETS)
    assert result["status"] == "warn"
    assert any(d["dimension"] == "per_day" for d in result["details"])


def test_governor_breach_per_run_at_limit():
    # exactly at limit → breach
    totals = {"per_run_cost_usd": 50.0, "per_day_cost_usd": 10.0}
    result = al.budget_governor(totals, BUDGETS)
    assert result["status"] == "breach"
    d = next(d for d in result["details"] if d["dimension"] == "per_run")
    assert d["over_by_usd"] == pytest.approx(0.0)


def test_governor_breach_per_run_over_limit():
    totals = {"per_run_cost_usd": 55.0, "per_day_cost_usd": 10.0}
    result = al.budget_governor(totals, BUDGETS)
    assert result["status"] == "breach"
    d = next(d for d in result["details"] if d["dimension"] == "per_run")
    assert d["over_by_usd"] == pytest.approx(5.0)


def test_governor_breach_per_day():
    totals = {"per_run_cost_usd": 5.0, "per_day_cost_usd": 600.0}
    result = al.budget_governor(totals, BUDGETS)
    assert result["status"] == "breach"
    assert any(d["dimension"] == "per_day" for d in result["details"])


def test_governor_breach_beats_warn():
    # per_run warns, per_day breaches → overall breach
    totals = {"per_run_cost_usd": 42.0, "per_day_cost_usd": 600.0}
    result = al.budget_governor(totals, BUDGETS)
    assert result["status"] == "breach"


# ---------------------------------------------------------------------------
# budget_governor — inert-degradation cases
# ---------------------------------------------------------------------------


def test_governor_inert_missing_per_day_total():
    # Only per_run provided; per_day absent → inert for that dimension
    totals = {"per_run_cost_usd": 60.0}
    result = al.budget_governor(totals, BUDGETS)
    assert result["status"] == "breach"
    assert all(d["dimension"] == "per_run" for d in result["details"])


def test_governor_inert_missing_per_run_total():
    totals = {"per_day_cost_usd": 600.0}
    result = al.budget_governor(totals, BUDGETS)
    assert result["status"] == "breach"
    assert all(d["dimension"] == "per_day" for d in result["details"])


def test_governor_inert_none_totals():
    totals = {"per_run_cost_usd": None, "per_day_cost_usd": None}
    result = al.budget_governor(totals, BUDGETS)
    assert result["status"] == "ok"
    assert result["details"] == []


def test_governor_inert_empty_budgets():
    # No caps at all → inert even with huge spend
    totals = {"per_run_cost_usd": 1_000.0, "per_day_cost_usd": 99_999.0}
    result = al.budget_governor(totals, {})
    assert result["status"] == "ok"
    assert result["details"] == []


def test_governor_inert_empty_caps():
    # caps key present but empty
    totals = {"per_run_cost_usd": 1_000.0, "per_day_cost_usd": 99_999.0}
    result = al.budget_governor(totals, {"caps": {}})
    assert result["status"] == "ok"


def test_governor_inert_zero_limit():
    # limit of 0 → guard fires, dimension is inert
    totals = {"per_run_cost_usd": 1.0, "per_day_cost_usd": 0.0}
    result = al.budget_governor(totals, {"caps": {"per_run": {"max_cost_usd": 0.0}}})
    assert result["status"] == "ok"


# ---------------------------------------------------------------------------
# evaluate_alerts with cost readings
# ---------------------------------------------------------------------------


def test_evaluate_cost_breach_per_run_fires_critical():
    readings = {"per_run_cost_usd": 60.0, "per_day_cost_usd": 10.0}
    alerts = al.evaluate_alerts(readings, TH, BUDGETS)
    cost = [a for a in alerts if a["metric"] == "COST"]
    assert len(cost) == 1
    assert cost[0]["severity"] == "critical"
    assert "per_run" in cost[0]["message"]


def test_evaluate_cost_breach_per_day_fires_critical():
    readings = {"per_run_cost_usd": 5.0, "per_day_cost_usd": 600.0}
    alerts = al.evaluate_alerts(readings, TH, BUDGETS)
    cost = [a for a in alerts if a["metric"] == "COST"]
    assert len(cost) == 1
    assert cost[0]["severity"] == "critical"
    assert "per_day" in cost[0]["message"]


def test_evaluate_cost_warn_fires_warning():
    # 82% of $50 → warn band
    readings = {"per_run_cost_usd": 41.0, "per_day_cost_usd": 5.0}
    alerts = al.evaluate_alerts(readings, TH, BUDGETS)
    cost = [a for a in alerts if a["metric"] == "COST"]
    assert len(cost) == 1
    assert cost[0]["severity"] == "warning"


def test_evaluate_cost_ok_no_alert():
    readings = {"per_run_cost_usd": 5.0, "per_day_cost_usd": 50.0}
    alerts = al.evaluate_alerts(readings, TH, BUDGETS)
    assert all(a["metric"] != "COST" for a in alerts)


def test_evaluate_cost_inert_none_readings():
    readings = {"per_run_cost_usd": None, "per_day_cost_usd": None}
    alerts = al.evaluate_alerts(readings, TH, BUDGETS)
    assert all(a["metric"] != "COST" for a in alerts)


def test_evaluate_cost_inert_no_budgets_arg():
    # budgets=None → no cost alert even with huge spend
    readings = {"per_run_cost_usd": 9_999.0, "per_day_cost_usd": 9_999.0}
    alerts = al.evaluate_alerts(readings, TH, budgets=None)
    assert all(a["metric"] != "COST" for a in alerts)


def test_evaluate_cost_inert_empty_budgets_arg():
    readings = {"per_run_cost_usd": 9_999.0, "per_day_cost_usd": 9_999.0}
    alerts = al.evaluate_alerts(readings, TH, budgets={})
    assert all(a["metric"] != "COST" for a in alerts)


def test_evaluate_cost_breach_sorted_critical_first():
    # critical COST alert must appear at index 0 in sorted output
    readings = {
        "t1_busy_fraction": 0.30,  # warning
        "per_run_cost_usd": 60.0,  # critical
    }
    alerts = al.evaluate_alerts(readings, TH, BUDGETS)
    assert alerts[0]["severity"] == "critical"


# ---------------------------------------------------------------------------
# Regression: existing alerting behaviour unchanged when budgets are passed
# ---------------------------------------------------------------------------


def test_regression_t1_still_fires():
    readings = {"t1_busy_fraction": 0.40, "per_run_cost_usd": None, "per_day_cost_usd": None}
    alerts = al.evaluate_alerts(readings, TH, BUDGETS)
    assert any(a["metric"] == "T1" for a in alerts)


def test_regression_t7_still_fires():
    alerts = al.evaluate_alerts({"t7_regressed": True}, TH, BUDGETS)
    assert any(a["metric"] == "T7" and a["severity"] == "critical" for a in alerts)


def test_regression_break_glass_still_fires():
    alerts = al.evaluate_alerts({"break_glass_active": True}, TH, BUDGETS)
    assert any(a["metric"] == "BREAK-GLASS" for a in alerts)


def test_regression_quiet_mode_drops_info():
    mixed = [
        {"severity": "info", "metric": "x", "message": "m"},
        {"severity": "warning", "metric": "COST", "message": "warn"},
        {"severity": "critical", "metric": "COST", "message": "breach"},
    ]
    filtered = al.filter_quiet(mixed)
    assert all(a["severity"] in {"warning", "critical"} for a in filtered)
    assert len(filtered) == 2


def test_regression_no_alerts_when_inert():
    readings = {"t1_busy_fraction": None, "memory_health": None, "break_glass_active": False,
                "per_run_cost_usd": None, "per_day_cost_usd": None}
    assert al.evaluate_alerts(readings, TH, BUDGETS) == []


# ---------------------------------------------------------------------------
# CLI smoke — runs clean with and without a budgets file
# ---------------------------------------------------------------------------


def test_cli_with_real_budgets(tmp_path):
    """CLI runs clean when pointing at the real config/budgets.yaml."""
    rc = al.main([
        "--events", str(tmp_path / "e.jsonl"),
        "--memory-store", str(tmp_path / "m.jsonl"),
        "--memory-config", str(REPO_ROOT / "config" / "memory_governance.yaml"),
        "--thresholds", str(REPO_ROOT / "config" / "alert_thresholds.yaml"),
        "--budgets", str(REPO_ROOT / "config" / "budgets.yaml"),
    ])
    assert rc == 0


def test_cli_with_absent_budgets(tmp_path):
    """CLI is inert (exit 0) when the budgets file is absent."""
    rc = al.main([
        "--events", str(tmp_path / "e.jsonl"),
        "--memory-store", str(tmp_path / "m.jsonl"),
        "--memory-config", str(REPO_ROOT / "config" / "memory_governance.yaml"),
        "--thresholds", str(REPO_ROOT / "config" / "alert_thresholds.yaml"),
        "--budgets", str(tmp_path / "no_budgets.yaml"),
    ])
    assert rc == 0
