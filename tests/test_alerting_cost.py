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


# ---------------------------------------------------------------------------
# DAS-1640 — gather_readings' per_day_cost_usd must be day-windowed, not a
# lifetime total mislabelled "today's spend" (the un-fixed sibling of the
# defect DAS-1632 fixed in loop_controller._per_day_budget_exceeded).
# ---------------------------------------------------------------------------

import datetime as _dt  # noqa: E402
import json as _json  # noqa: E402

import loop_controller as _lc  # noqa: E402

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
    """Append one opus span event — same shape test_loop_controller.py uses."""
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
    """Reproduces the SRE Lead's exact review finding: an event store with
    ~$15 spend on the PREVIOUS UTC day plus ~$2 spend TODAY must report
    per_day_cost_usd ~= $2.00 (today only), never the ~$17.00 lifetime total
    the un-fixed `raw_estimated_cost_usd`-from-unwindowed-aggregate_spans
    defect produced.
    """
    budgets = _write_pricing_budgets(tmp_path)
    events = tmp_path / "events.jsonl"
    # ~3M input tokens of opus on the prior day => 3,000,000/1e6 * $5 = $15.00
    _write_span(events, "2026-07-23T09:00:00Z", 3_000_000, 0)
    # ~0.4M input tokens of opus today => 0.4 * $5 = $2.00
    _write_span(events, "2026-07-24T09:00:00Z", 400_000, 0, run_id="r2")

    # Pin "now" inside gather_readings so the test is deterministic regardless
    # of wall-clock day.
    fixed_now = _dt.datetime(2026, 7, 24, 12, 0, 0, tzinfo=_dt.UTC)

    class _FixedDateTime(_dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed_now if tz is not None else fixed_now.replace(tzinfo=None)

    monkeypatch.setattr(al, "datetime", _FixedDateTime)

    # Sanity: lifetime aggregation genuinely sees the full $17 (proves the
    # fixture reproduces the reviewer's premise — a vacuous fixture would
    # already read ~$2 lifetime and the test would prove nothing).
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
    """Failure-isolation: if `loop_controller._window_start` can't be imported,
    per_day_cost_usd degrades to None (inert) rather than silently reverting
    to an unwindowed lifetime read."""
    budgets = _write_pricing_budgets(tmp_path)
    events = tmp_path / "events.jsonl"
    _write_span(events, "2026-07-24T09:00:00Z", 400_000, 0)

    monkeypatch.setattr(al, "_WINDOW_START_AVAILABLE", False)
    readings = al.gather_readings(events, tmp_path / "mem.jsonl", REPO_ROOT / "config" / "memory_governance.yaml", budgets)
    assert readings["per_day_cost_usd"] is None


# ---------------------------------------------------------------------------
# DAS-1640 item 2 — future-dated spans: decision = (b) lower-bound-only is
# DELIBERATE (see ticket log for full reasoning). This test proves the
# decision is applied IDENTICALLY across all three readers that consult
# `_window_start`-derived windows: the per-day tick rail, the monthly tick
# rail, and this alerting reading. A future-dated span counts toward "today"
# / "this month" in all three, or none — never a mismatched subset.
# ---------------------------------------------------------------------------


def test_future_dated_span_treated_identically_across_all_three_readers(tmp_path, monkeypatch):
    budgets = _write_pricing_budgets(tmp_path)
    events = tmp_path / "events.jsonl"
    # A single span dated ~1 year in the future relative to "now".
    _write_span(events, "2027-07-24T09:00:00Z", 1_000_000, 0)  # $5.00 of opus

    fixed_now = _dt.datetime(2026, 7, 24, 12, 0, 0, tzinfo=_dt.UTC)

    class _FixedDateTime(_dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed_now if tz is not None else fixed_now.replace(tzinfo=None)

    monkeypatch.setattr(al, "datetime", _FixedDateTime)

    # Reader 1 — alerting's per_day_cost_usd.
    readings = al.gather_readings(events, tmp_path / "mem.jsonl", REPO_ROOT / "config" / "memory_governance.yaml", budgets)
    alerting_counts_it = readings["per_day_cost_usd"] is not None and readings["per_day_cost_usd"] > 0

    # Reader 2 — the per-day tick rail (via a cap low enough that ONLY the
    # future-dated span's inclusion/exclusion decides the verdict).
    per_day_budgets = tmp_path / "per_day_budgets.yaml"
    per_day_budgets.write_text(
        "mustaqil:\n  caps:\n    per_day:\n      max_cost_usd: 1.00\n" + _PRICING_YAML,
        encoding="utf-8",
    )
    per_day_rail_counts_it = _lc._per_day_budget_exceeded(per_day_budgets, events, now=fixed_now)

    # Reader 3 — the monthly tick rail (same shape: a plan cap tight enough
    # that only the future span's inclusion decides it).
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

    # All three must agree: either all three count the future-dated span
    # (lower-bound-only, decision (b)), or none do. Never a mismatched subset.
    verdicts = {alerting_counts_it, per_day_rail_counts_it, monthly_rail_counts_it}
    assert len(verdicts) == 1, (
        f"future-dated span treated inconsistently across readers: "
        f"alerting={alerting_counts_it} per_day_rail={per_day_rail_counts_it} "
        f"monthly_rail={monthly_rail_counts_it}"
    )
    # Pin the actual decision (b): lower-bound-only means it DOES count.
    assert verdicts == {True}, "decision (b) (lower-bound-only) means a future-dated span IS counted"
