#!/usr/bin/env python3

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import alerting as al

BUDGETS = {
    "caps": {
        "per_run": {"max_cost_usd": 50.0},
        "per_day": {"max_cost_usd": 500.0},
    }
}


TH = {"t1_busy_min": 0.60, "memory_health_min": 0.80}


def test_governor_ok_both_dimensions():
    totals = {"per_run_cost_usd": 10.0, "per_day_cost_usd": 50.0}
    result = al.budget_governor(totals, BUDGETS)
    assert result["status"] == "ok"
    assert result["details"] == []


def test_governor_warn_per_run():

    totals = {"per_run_cost_usd": 41.0, "per_day_cost_usd": 10.0}
    result = al.budget_governor(totals, BUDGETS)
    assert result["status"] == "warn"
    dims = {d["dimension"] for d in result["details"]}
    assert "per_run" in dims
    assert "per_day" not in dims


def test_governor_warn_per_day():

    totals = {"per_run_cost_usd": 5.0, "per_day_cost_usd": 410.0}
    result = al.budget_governor(totals, BUDGETS)
    assert result["status"] == "warn"
    assert any(d["dimension"] == "per_day" for d in result["details"])


def test_governor_breach_per_run_at_limit():

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

    totals = {"per_run_cost_usd": 42.0, "per_day_cost_usd": 600.0}
    result = al.budget_governor(totals, BUDGETS)
    assert result["status"] == "breach"


def test_governor_inert_missing_per_day_total():

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

    totals = {"per_run_cost_usd": 1_000.0, "per_day_cost_usd": 99_999.0}
    result = al.budget_governor(totals, {})
    assert result["status"] == "ok"
    assert result["details"] == []


def test_governor_inert_empty_caps():

    totals = {"per_run_cost_usd": 1_000.0, "per_day_cost_usd": 99_999.0}
    result = al.budget_governor(totals, {"caps": {}})
    assert result["status"] == "ok"


def test_governor_inert_zero_limit():

    totals = {"per_run_cost_usd": 1.0, "per_day_cost_usd": 0.0}
    result = al.budget_governor(totals, {"caps": {"per_run": {"max_cost_usd": 0.0}}})
    assert result["status"] == "ok"


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

    readings = {"per_run_cost_usd": 9_999.0, "per_day_cost_usd": 9_999.0}
    alerts = al.evaluate_alerts(readings, TH, budgets=None)
    assert all(a["metric"] != "COST" for a in alerts)


def test_evaluate_cost_inert_empty_budgets_arg():
    readings = {"per_run_cost_usd": 9_999.0, "per_day_cost_usd": 9_999.0}
    alerts = al.evaluate_alerts(readings, TH, budgets={})
    assert all(a["metric"] != "COST" for a in alerts)


def test_evaluate_cost_breach_sorted_critical_first():

    readings = {
        "t1_busy_fraction": 0.30,
        "per_run_cost_usd": 60.0,
    }
    alerts = al.evaluate_alerts(readings, TH, BUDGETS)
    assert alerts[0]["severity"] == "critical"


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


def _seed_events(tmp_path):
    import json as _js
    path = tmp_path / "e.jsonl"
    path.write_text(
        _js.dumps({
            "event_type": "run_end", "run_id": "R1",
            "created_at": "2026-07-04T10:10:00Z",
            "model": "sonnet", "outcome": "success",
        }) + "\n",
        encoding="utf-8",
    )
    return path


def test_cli_with_real_budgets(tmp_path):
    rc = al.main([
        "--events", str(_seed_events(tmp_path)),
        "--memory-store", str(tmp_path / "m.jsonl"),
        "--memory-config", str(REPO_ROOT / "config" / "memory_governance.yaml"),
        "--thresholds", str(REPO_ROOT / "config" / "alert_thresholds.yaml"),
        "--budgets", str(REPO_ROOT / "config" / "budgets.yaml"),
    ])
    assert rc == al.CliExit.HEALTHY


def test_cli_with_absent_budgets(tmp_path):
    rc = al.main([
        "--events", str(_seed_events(tmp_path)),
        "--memory-store", str(tmp_path / "m.jsonl"),
        "--memory-config", str(REPO_ROOT / "config" / "memory_governance.yaml"),
        "--thresholds", str(REPO_ROOT / "config" / "alert_thresholds.yaml"),
        "--budgets", str(tmp_path / "no_budgets.yaml"),
    ])
    assert rc == al.CliExit.HEALTHY


def test_cli_with_no_events_at_all_is_no_data_not_healthy(tmp_path):
    rc = al.main([
        "--events", str(tmp_path / "absent.jsonl"),
        "--memory-store", str(tmp_path / "m.jsonl"),
        "--memory-config", str(REPO_ROOT / "config" / "memory_governance.yaml"),
        "--thresholds", str(REPO_ROOT / "config" / "alert_thresholds.yaml"),
        "--budgets", str(REPO_ROOT / "config" / "budgets.yaml"),
    ])
    assert rc == al.CliExit.NO_DATA
    assert rc != al.CliExit.HEALTHY


import datetime as _dt
import json as _json

import loop_controller as _lc

_PRICING_YAML = """
tiers:
  opus:
    input_per_1m: 5.00
    cached_input_per_1m: 0.50
    output_per_1m: 25.00
  sonnet:
    input_per_1m: 3.00
    cached_input_per_1m: 0.30
    output_per_1m: 15.00
"""


def _write_pricing_budgets(tmp_path) -> Path:
    p = tmp_path / "budgets.yaml"
    p.write_text(_PRICING_YAML, encoding="utf-8")
    return p


def _write_span(path: Path, created_at: str, input_tokens: int, output_tokens: int, run_id: str = "r1") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ev = {
        "event_type": "span",
        "ticket_id": "DAS-9999",
        "trace_id": "DAS-9999",
        "span_id": "span-001",
        "kind": "invoke_agent",
        "gen_ai.agent.name": "sre-eng",
        "gen_ai.request.model": "opus",
        "start": created_at,
        "end": created_at,
        "duration_ms": 0,
        "gen_ai.usage.input_tokens": input_tokens,
        "gen_ai.usage.output_tokens": output_tokens,
        "gen_ai.usage.cached_input_tokens": 0,
        "cached": False,
        "status": "ok",
        "created_at": created_at,
        "run_id": run_id,
    }
    with path.open("a", encoding="utf-8") as fh:
        fh.write(_json.dumps(ev) + "\n")


def test_gather_readings_per_day_cost_windowed_not_lifetime(tmp_path, monkeypatch):
    budgets = _write_pricing_budgets(tmp_path)
    events = tmp_path / "events.jsonl"

    _write_span(events, "2026-07-23T09:00:00Z", 3_000_000, 0)

    _write_span(events, "2026-07-24T09:00:00Z", 400_000, 0, run_id="r2")


    fixed_now = _dt.datetime(2026, 7, 24, 12, 0, 0, tzinfo=_dt.UTC)

    class _FixedDateTime(_dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed_now if tz is not None else fixed_now.replace(tzinfo=None)

    monkeypatch.setattr(al, "datetime", _FixedDateTime)


    from cost.cost_ledger import aggregate_spans
    lifetime_ledger = aggregate_spans(events, budgets)
    assert lifetime_ledger is not None
    assert lifetime_ledger.raw_estimated_cost_usd == pytest.approx(17.0)

    readings = al.gather_readings(events, tmp_path / "mem.jsonl", REPO_ROOT / "config" / "memory_governance.yaml", budgets)
    assert readings["per_day_cost_usd"] == pytest.approx(2.0), (
        f"expected windowed today-only spend ~$2.00, got {readings['per_day_cost_usd']!r} "
        "(a value near $17.00 means gather_readings regressed back to the lifetime-total defect)"
    )


def test_gather_readings_per_day_cost_none_when_window_start_unavailable(tmp_path, monkeypatch):
    budgets = _write_pricing_budgets(tmp_path)
    events = tmp_path / "events.jsonl"
    _write_span(events, "2026-07-24T09:00:00Z", 400_000, 0)

    monkeypatch.setattr(al, "_WINDOW_START_AVAILABLE", False)
    readings = al.gather_readings(events, tmp_path / "mem.jsonl", REPO_ROOT / "config" / "memory_governance.yaml", budgets)
    assert readings["per_day_cost_usd"] is None


def test_future_dated_span_treated_identically_across_all_three_readers(tmp_path, monkeypatch):
    budgets = _write_pricing_budgets(tmp_path)
    events = tmp_path / "events.jsonl"

    _write_span(events, "2027-07-24T09:00:00Z", 1_000_000, 0)

    fixed_now = _dt.datetime(2026, 7, 24, 12, 0, 0, tzinfo=_dt.UTC)

    class _FixedDateTime(_dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed_now if tz is not None else fixed_now.replace(tzinfo=None)

    monkeypatch.setattr(al, "datetime", _FixedDateTime)


    readings = al.gather_readings(events, tmp_path / "mem.jsonl", REPO_ROOT / "config" / "memory_governance.yaml", budgets)
    alerting_counts_it = readings["per_day_cost_usd"] is not None and readings["per_day_cost_usd"] > 0


    per_day_budgets = tmp_path / "per_day_budgets.yaml"
    per_day_budgets.write_text(
        "mustaqil:\n  caps:\n    per_day:\n      max_cost_usd: 1.00\n" + _PRICING_YAML,
        encoding="utf-8",
    )
    per_day_rail_counts_it = _lc._per_day_budget_exceeded(per_day_budgets, events, now=fixed_now)


    monthly_budgets = tmp_path / "monthly_budgets.yaml"
    monthly_budgets.write_text(
        "mustaqil:\n"
        "  monthly_credit_ceiling:\n"
        "    plan_credit_usd:\n"
        "      pro: 1.00\n"
        "    active_plan: pro\n"
        "    on_exhaustion: sanctioned_pause\n"
        "    metered_overflow: false\n" + _PRICING_YAML,
        encoding="utf-8",
    )
    monthly_rail_counts_it = _lc._monthly_credit_exhausted(monthly_budgets, events, now=fixed_now)


    verdicts = {alerting_counts_it, per_day_rail_counts_it, monthly_rail_counts_it}
    assert len(verdicts) == 1, (
        f"future-dated span treated inconsistently across readers: "
        f"alerting={alerting_counts_it} per_day_rail={per_day_rail_counts_it} "
        f"monthly_rail={monthly_rail_counts_it}"
    )

    assert verdicts == {True}, "decision (b) (lower-bound-only) means a future-dated span IS counted"
