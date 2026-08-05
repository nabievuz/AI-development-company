#!/usr/bin/env python3

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import loop_controller as lc

T = lc.DEFAULT_TARGETS


def _clean_day():
    return {"t1": 0.65, "t2": 0.10, "t3": 7, "t4": 0.30, "t5": 0.999, "t7_holds": True}


def _approved_record(frm="shadow", to="measured", approver="founder"):
    return {"gate_6_record": {
        "change_type": "capability_promotion",
        "proposed_change": {"from_mode": frm, "to_mode": to},
        "guardrails": {"max_quality_drop": 0},
        "approval": {"approved_by": approver},
    }}


def test_ladder_one_rung():
    assert lc.next_mode("shadow") == "measured"
    assert lc.next_mode("measured") == "limited_live"
    assert lc.next_mode("limited_live") == "full"
    assert lc.next_mode("full") is None
    assert lc.next_mode("bogus") is None


def test_clean_days_counts_trailing_streak():
    history = [{"t1": 0.1, "t7_holds": False}] + [_clean_day() for _ in range(7)]
    assert lc.clean_live_days(history, T) == 7


def test_a_bad_day_breaks_the_streak():
    history = [_clean_day() for _ in range(5)] + [{"t1": 0.1, "t7_holds": False}] + [_clean_day() for _ in range(2)]
    assert lc.clean_live_days(history, T) == 2


def test_day_not_clean_if_t7_drops():
    day = dict(_clean_day(), t7_holds=False)
    assert lc.day_is_clean(day, T) is False


def test_approved_record_required():
    assert lc.has_approved_promotion_record([_approved_record()], "shadow", "measured") is True


def test_unapproved_record_does_not_count():
    rec = _approved_record(approver="")
    assert lc.has_approved_promotion_record([rec], "shadow", "measured") is False


def test_wrong_rung_record_does_not_count():
    assert lc.has_approved_promotion_record([_approved_record(to="full")], "shadow", "measured") is False


def test_not_eligible_with_no_evidence():
    r = lc.evaluate_promotion("shadow", [], [], T)
    assert r["eligible"] is False
    assert len(r["blockers"]) == 2


def test_not_eligible_with_clean_days_but_no_record():
    r = lc.evaluate_promotion("shadow", [], [_clean_day() for _ in range(7)], T)
    assert r["eligible"] is False
    assert any("no human-approved" in b for b in r["blockers"])


def test_not_eligible_with_record_but_insufficient_days():
    r = lc.evaluate_promotion("shadow", [_approved_record()], [_clean_day() for _ in range(3)], T)
    assert r["eligible"] is False
    assert any("insufficient clean live evidence" in b for b in r["blockers"])


def test_eligible_only_with_both():
    r = lc.evaluate_promotion("shadow", [_approved_record()], [_clean_day() for _ in range(7)], T)
    assert r["eligible"] is True and r["target"] == "measured"


def test_full_mode_not_eligible():
    r = lc.evaluate_promotion("full", [], [_clean_day() for _ in range(30)], T)
    assert r["eligible"] is False and any("already at 'full'" in b for b in r["blockers"])


def test_promotion_draft_is_unapproved():
    rec = lc.promotion_draft("shadow", "measured", "2026-06-22T00:00:00Z")["gate_6_record"]
    assert rec["approval"]["approved_by"] == ""
    assert rec["guardrails"]["max_quality_drop"] == 0
    assert rec["rollout"]["mode"] == "shadow"


def test_cli_inert_loop_stays_shadow():

    assert lc.main([]) == 0


def test_cli_does_not_mutate_loop_config():
    before = (REPO_ROOT / "config" / "loop.yaml").read_text()
    lc.main(["--propose"])
    assert (REPO_ROOT / "config" / "loop.yaml").read_text() == before


def test_whitespace_approver_rejected():
    assert lc.has_approved_promotion_record([_approved_record(approver="   ")], "shadow", "measured") is False


def test_day_is_clean_non_dict_is_false():
    assert lc.day_is_clean(None, T) is False
    assert lc.clean_live_days([None, "x"], T) == 0


def _write_budgets(tmp_path, *, active_plan=None, plan_credit_usd=None):
    plan_credit_usd = plan_credit_usd or {"pro": 20, "max_5x": 100, "max_20x": 200}
    lines = ["mustaqil:", "  monthly_credit_ceiling:", "    plan_credit_usd:"]
    for k, v in plan_credit_usd.items():
        lines.append(f"      {k}: {v}")
    if active_plan is not None:
        lines.append(f"    active_plan: {active_plan}")
    lines.append("    on_exhaustion: sanctioned_pause")
    lines.append("    metered_overflow: false")
    p = tmp_path / "budgets.yaml"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def test_monthly_credit_exhausted_false_when_active_plan_undeclared(tmp_path):


    budgets = _write_budgets(tmp_path, active_plan=None)
    assert lc._monthly_credit_exhausted(budgets, tmp_path / "events.jsonl") is False


def test_monthly_credit_exhausted_false_when_budgets_missing(tmp_path):
    assert lc._monthly_credit_exhausted(tmp_path / "nope.yaml", tmp_path / "events.jsonl") is False


def test_monthly_credit_exhausted_with_explicit_credit_state_exhausted(tmp_path):
    import ws_b_admission as wba

    budgets = _write_budgets(tmp_path, active_plan="pro")
    state = wba.CreditState(plan="pro", used_usd=20.0)
    assert lc._monthly_credit_exhausted(budgets, tmp_path / "events.jsonl", credit_state=state) is True


def test_monthly_credit_exhausted_with_explicit_credit_state_not_exhausted(tmp_path):
    import ws_b_admission as wba

    budgets = _write_budgets(tmp_path, active_plan="pro")
    state = wba.CreditState(plan="pro", used_usd=1.0)
    assert lc._monthly_credit_exhausted(budgets, tmp_path / "events.jsonl", credit_state=state) is False


def test_monthly_credit_exhausted_does_not_inherit_max_20x_default(tmp_path):


    budgets = _write_budgets(tmp_path, active_plan=None)
    assert lc._monthly_credit_exhausted(budgets, tmp_path / "events.jsonl") is False


def test_tick_surfaces_monthly_credit_exhausted_rail(tmp_path):
    budgets = _write_budgets(tmp_path, active_plan=None)
    r = lc.tick(budgets_path=budgets, metrics_history=tmp_path / "nope.jsonl",
                events_path=tmp_path / "events.jsonl")
    assert "monthly_credit_exhausted" in r["safety_rails"]
    assert r["safety_rails"]["monthly_credit_exhausted"] is False


def test_tick_never_calls_admit_or_gated_admit(monkeypatch, tmp_path):
    import ws_b_admission as wba

    def _boom(*a, **k):
        raise AssertionError("tick must not call admit()/gated_admit()")

    monkeypatch.setattr(wba, "admit", _boom)
    monkeypatch.setattr(wba, "gated_admit", _boom)
    budgets = _write_budgets(tmp_path, active_plan="pro")
    r = lc.tick(budgets_path=budgets, metrics_history=tmp_path / "nope.jsonl",
                events_path=tmp_path / "events.jsonl")
    assert r["safety_rails"]["monthly_credit_exhausted"] in (True, False)


import datetime as _dt
import json as _json


def _write_budgets_with_pricing(tmp_path, *, active_plan=None, plan_credit_usd=None):
    plan_credit_usd = plan_credit_usd or {"pro": 20, "max_5x": 100, "max_20x": 200}
    lines = [
        "mustaqil:",
        "  monthly_credit_ceiling:",
        "    plan_credit_usd:",
    ]
    for k, v in plan_credit_usd.items():
        lines.append(f"      {k}: {v}")
    if active_plan is not None:
        lines.append(f"    active_plan: {active_plan}")
    lines.append("    on_exhaustion: sanctioned_pause")
    lines.append("    metered_overflow: false")
    lines.append("tiers:")
    lines.append("  opus:")
    lines.append("    input_per_1m: 5.00")
    lines.append("    cached_input_per_1m: 0.50")
    lines.append("    output_per_1m: 25.00")
    lines.append("  sonnet:")
    lines.append("    input_per_1m: 3.00")
    lines.append("    cached_input_per_1m: 0.30")
    lines.append("    output_per_1m: 15.00")
    lines.append("  haiku:")
    lines.append("    input_per_1m: 1.00")
    lines.append("    cached_input_per_1m: 0.10")
    lines.append("    output_per_1m: 5.00")
    p = tmp_path / "budgets.yaml"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def _write_span_events(path, spans):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for created_at, input_tokens, output_tokens in spans:
            ev = {
                "event_type": "span",
                "ticket_id": "DAS-9999",
                "trace_id": "DAS-9999",
                "span_id": "span-001",
                "parent_span_id": None,
                "kind": "invoke_agent",
                "gen_ai.agent.name": "backend-eng-2",
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
                "run_id": "r1",
            }
            fh.write(_json.dumps(ev) + "\n")


def test_window_start_month_and_day():
    now = _dt.datetime(2026, 7, 24, 15, 30, 0, tzinfo=_dt.UTC)
    assert lc._window_start(now, unit="month") == _dt.datetime(2026, 7, 1, 0, 0, 0)
    assert lc._window_start(now, unit="day") == _dt.datetime(2026, 7, 24, 0, 0, 0)


def test_window_start_rejects_unknown_unit():
    import pytest as _pytest

    with _pytest.raises(ValueError):
        lc._window_start(_dt.datetime(2026, 7, 24, tzinfo=_dt.UTC), unit="year")


def test_monthly_credit_exhausted_reproduces_D1_before_fix_would_have_been_true(tmp_path):
    budgets = _write_budgets_with_pricing(tmp_path, active_plan="pro")
    events = tmp_path / "events.jsonl"

    _write_span_events(events, [("2025-01-15T12:00:00Z", 10_000_000, 3_000_000)])


    scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    from cost.cost_ledger import aggregate_spans
    lifetime_ledger = aggregate_spans(events, budgets)
    assert lifetime_ledger is not None
    assert lifetime_ledger.raw_estimated_cost_usd >= 20.0

    now = _dt.datetime(2026, 7, 24, 12, 0, 0, tzinfo=_dt.UTC)
    assert lc._monthly_credit_exhausted(budgets, events, now=now) is False


def test_monthly_credit_exhausted_true_when_spend_is_in_current_month(tmp_path):
    budgets = _write_budgets_with_pricing(tmp_path, active_plan="pro")
    events = tmp_path / "events.jsonl"
    _write_span_events(events, [("2026-07-10T09:00:00Z", 10_000_000, 3_000_000)])

    now = _dt.datetime(2026, 7, 24, 12, 0, 0, tzinfo=_dt.UTC)
    assert lc._monthly_credit_exhausted(budgets, events, now=now) is True


def test_monthly_credit_exhausted_mixed_months_only_current_counts(tmp_path):
    budgets = _write_budgets_with_pricing(tmp_path, active_plan="pro")
    events = tmp_path / "events.jsonl"
    _write_span_events(events, [
        ("2025-01-15T12:00:00Z", 10_000_000, 3_000_000),
        ("2026-07-05T08:00:00Z", 100, 50),
    ])

    now = _dt.datetime(2026, 7, 24, 12, 0, 0, tzinfo=_dt.UTC)
    assert lc._monthly_credit_exhausted(budgets, events, now=now) is False


def _write_per_day_budgets_with_pricing(tmp_path, *, max_cost_usd):
    lines = [
        "mustaqil:",
        "  caps:",
        "    per_day:",
        f"      max_cost_usd: {max_cost_usd}",
        "tiers:",
        "  opus:",
        "    input_per_1m: 5.00",
        "    cached_input_per_1m: 0.50",
        "    output_per_1m: 25.00",
        "  sonnet:",
        "    input_per_1m: 3.00",
        "    cached_input_per_1m: 0.30",
        "    output_per_1m: 15.00",
        "  haiku:",
        "    input_per_1m: 1.00",
        "    cached_input_per_1m: 0.10",
        "    output_per_1m: 5.00",
    ]
    p = tmp_path / "budgets.yaml"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def test_per_day_budget_resolves_from_mustaqil_key_not_org_informational_block(tmp_path):
    lines = [
        "caps:",
        "  per_day:",
        "    max_cost_usd: 500.00",
        "mustaqil:",
        "  caps:",
        "    per_day:",
        "      max_cost_usd: 15.00",
        "tiers:",
        "  opus:",
        "    input_per_1m: 5.00",
        "    cached_input_per_1m: 0.50",
        "    output_per_1m: 25.00",
    ]
    budgets = tmp_path / "budgets.yaml"
    budgets.write_text("\n".join(lines) + "\n", encoding="utf-8")

    events = tmp_path / "events.jsonl"

    _write_span_events(events, [("2026-07-24T09:00:00Z", 4_000_000, 0)])

    now = _dt.datetime(2026, 7, 24, 12, 0, 0, tzinfo=_dt.UTC)
    assert lc._per_day_budget_exceeded(budgets, events, now=now) is True, (
        "rail did not resolve mustaqil.caps.per_day.max_cost_usd — it must "
        "breach at $20 spend against the $15 SI-5 ceiling even though the "
        "$500 org-informational ceiling is untouched"
    )


def test_per_day_budget_reproduces_defect_before_fix_would_have_been_true(tmp_path):
    budgets = _write_per_day_budgets_with_pricing(tmp_path, max_cost_usd=20)
    events = tmp_path / "events.jsonl"

    _write_span_events(events, [("2026-07-23T12:00:00Z", 10_000_000, 3_000_000)])


    scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    from cost.cost_ledger import aggregate_spans
    lifetime_ledger = aggregate_spans(events, budgets)
    assert lifetime_ledger is not None
    assert lifetime_ledger.raw_estimated_cost_usd >= 20.0

    now = _dt.datetime(2026, 7, 24, 12, 0, 0, tzinfo=_dt.UTC)
    assert lc._per_day_budget_exceeded(budgets, events, now=now) is False


def test_per_day_budget_true_when_spend_is_today(tmp_path):
    budgets = _write_per_day_budgets_with_pricing(tmp_path, max_cost_usd=20)
    events = tmp_path / "events.jsonl"
    _write_span_events(events, [("2026-07-24T09:00:00Z", 10_000_000, 3_000_000)])

    now = _dt.datetime(2026, 7, 24, 12, 0, 0, tzinfo=_dt.UTC)
    assert lc._per_day_budget_exceeded(budgets, events, now=now) is True


def test_per_day_budget_mixed_days_only_today_counts(tmp_path):
    budgets = _write_per_day_budgets_with_pricing(tmp_path, max_cost_usd=20)
    events = tmp_path / "events.jsonl"
    _write_span_events(events, [
        ("2026-07-23T12:00:00Z", 10_000_000, 3_000_000),
        ("2026-07-24T08:00:00Z", 100, 50),
    ])

    now = _dt.datetime(2026, 7, 24, 12, 0, 0, tzinfo=_dt.UTC)
    assert lc._per_day_budget_exceeded(budgets, events, now=now) is False


def test_per_day_budget_boundary_instant_is_included(tmp_path):
    budgets = _write_per_day_budgets_with_pricing(tmp_path, max_cost_usd=1)
    events = tmp_path / "events.jsonl"

    _write_span_events(events, [("2026-07-24T00:00:00Z", 100_000, 30_000)])

    now = _dt.datetime(2026, 7, 24, 12, 0, 0, tzinfo=_dt.UTC)
    scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    from cost.cost_ledger import aggregate_spans
    day_start = lc._window_start(now, unit="day")
    windowed_ledger = aggregate_spans(events, budgets, since=day_start)
    assert windowed_ledger is not None
    assert windowed_ledger.raw_estimated_cost_usd > 0


def test_monthly_credit_boundary_instant_is_included(tmp_path):
    budgets = _write_budgets_with_pricing(tmp_path, active_plan="pro")
    events = tmp_path / "events.jsonl"
    _write_span_events(events, [("2026-07-01T00:00:00Z", 10_000_000, 3_000_000)])

    now = _dt.datetime(2026, 7, 24, 12, 0, 0, tzinfo=_dt.UTC)


    assert lc._monthly_credit_exhausted(budgets, events, now=now) is True


def test_tick_threads_now_once_into_per_day_budget(monkeypatch, tmp_path):
    seen = {}
    real_per_day = lc._per_day_budget_exceeded

    def _spy(budgets_path, events_path, *, now=None):
        seen["now"] = now
        return real_per_day(budgets_path, events_path, now=now)

    monkeypatch.setattr(lc, "_per_day_budget_exceeded", _spy)
    budgets = _write_per_day_budgets_with_pricing(tmp_path, max_cost_usd=20)
    injected_now = _dt.datetime(2026, 7, 24, 3, 0, 0, tzinfo=_dt.UTC)
    lc.tick(budgets_path=budgets, metrics_history=tmp_path / "nope.jsonl",
            events_path=tmp_path / "events.jsonl", now=injected_now)
    assert seen["now"] == injected_now


def test_unreadable_experiment_does_not_crash(tmp_path):
    exp = tmp_path / "experiments"
    exp.mkdir()
    (exp / "bad.yaml").mkdir()
    assert lc._load_records(exp) == []
    rc = lc.main(["--loop-config", str(REPO_ROOT / "config" / "loop.yaml"),
                  "--experiments", str(exp), "--metrics-history", str(tmp_path / "nope.jsonl")])
    assert rc == 0


def test_tick_no_alert_on_a_normal_tick(tmp_path):
    r = lc.tick(metrics_history=tmp_path / "nope.jsonl", events_path=tmp_path / "events.jsonl")
    assert r["safety_rails"]["per_day_budget_exceeded"] is False
    assert r["safety_rails"]["monthly_credit_exhausted"] is False
    assert r["alert"] is None


def test_tick_emits_alert_on_per_day_trip(tmp_path):
    budgets = _write_per_day_budgets_with_pricing(tmp_path, max_cost_usd=1)
    events = tmp_path / "events.jsonl"
    _write_span_events(events, [("2026-07-24T09:00:00Z", 10_000_000, 3_000_000)])

    now = _dt.datetime(2026, 7, 24, 12, 0, 0, tzinfo=_dt.UTC)
    r = lc.tick(budgets_path=budgets, metrics_history=tmp_path / "nope.jsonl", events_path=events, now=now)
    assert r["safety_rails"]["per_day_budget_exceeded"] is True
    assert r["alert"] is not None
    assert r["alert"]["severity"] == "info"
    assert r["alert"]["metric"] == "SI-5"
    assert "per-day budget cap" in r["alert"]["message"]

    assert r["alert"]["severity"] != "critical"


def test_tick_emits_alert_on_monthly_trip(tmp_path):
    budgets = _write_budgets_with_pricing(tmp_path, active_plan="pro")
    events = tmp_path / "events.jsonl"
    _write_span_events(events, [("2026-07-10T09:00:00Z", 10_000_000, 3_000_000)])

    now = _dt.datetime(2026, 7, 24, 12, 0, 0, tzinfo=_dt.UTC)
    r = lc.tick(budgets_path=budgets, metrics_history=tmp_path / "nope.jsonl", events_path=events, now=now)
    assert r["safety_rails"]["monthly_credit_exhausted"] is True
    assert r["alert"] is not None
    assert r["alert"]["severity"] == "info"
    assert r["alert"]["metric"] == "SI-5"
    assert "monthly credit ceiling" in r["alert"]["message"]


def test_alert_wiring_does_not_change_the_decision(tmp_path):
    budgets = _write_per_day_budgets_with_pricing(tmp_path, max_cost_usd=1)
    events = tmp_path / "events.jsonl"
    _write_span_events(events, [("2026-07-24T09:00:00Z", 10_000_000, 3_000_000)])
    now = _dt.datetime(2026, 7, 24, 12, 0, 0, tzinfo=_dt.UTC)

    with_alert = lc.tick(budgets_path=budgets, metrics_history=tmp_path / "nope.jsonl",
                          events_path=events, now=now)
    assert with_alert["alert"] is not None

    import builtins
    real_import = builtins.__import__

    def _no_alerting(name, *a, **k):
        if name == "alerting":
            raise ImportError("simulated: alert wiring absent")
        return real_import(name, *a, **k)

    builtins.__import__ = _no_alerting
    try:
        without_alert = lc.tick(budgets_path=budgets, metrics_history=tmp_path / "nope.jsonl",
                                 events_path=events, now=now)
    finally:
        builtins.__import__ = real_import

    assert without_alert["alert"] is None

    assert without_alert["decision"] == with_alert["decision"]
    assert without_alert["safety_rails"] == with_alert["safety_rails"]
    assert without_alert["promotion"] == with_alert["promotion"]
    assert without_alert["mode"] == with_alert["mode"]


def test_sanctioned_pause_alert_severity_distinct_from_critical_cost_breach():
    import alerting as al

    sanctioned = al.sanctioned_pause_alert(True, False)
    assert sanctioned["severity"] == "info"

    cost_breach = al.evaluate_alerts(
        {"per_day_cost_usd": 100.0},
        thresholds={},
        budgets={"caps": {"per_day": {"max_cost_usd": 10.0}}},
    )
    assert any(a["severity"] == "critical" and a["metric"] == "COST" for a in cost_breach)


    assert al.filter_quiet([sanctioned]) == []
    assert al.filter_quiet(cost_breach) == cost_breach


def test_sanctioned_pause_alert_none_when_both_rails_cold():
    import alerting as al

    assert al.sanctioned_pause_alert(False, False) is None


def test_flow_router_decisions_closed_alphabet_unchanged():
    import flow_router

    assert frozenset({"dispatch", "validate", "idle"}) == flow_router.DECISIONS


def _real_ceiling_cfg():
    from ws_b_admission import load_mustaqil_budgets

    budgets = load_mustaqil_budgets(REPO_ROOT / "config" / "budgets.yaml")
    return (budgets.get("monthly_credit_ceiling") or {}), budgets


def test_real_budgets_declares_a_resolvable_active_plan():
    ceiling, _ = _real_ceiling_cfg()
    active_plan = ceiling.get("active_plan")
    plan_credit_usd = ceiling.get("plan_credit_usd") or {}
    assert isinstance(active_plan, str) and active_plan.strip(), (
        "active_plan must be declared for the FR-004 outer ceiling to be enforceable"
    )
    assert active_plan in plan_credit_usd, (
        f"declared active_plan {active_plan!r} must be a key in plan_credit_usd "
        f"{sorted(plan_credit_usd)} — otherwise the ceiling resolves to nothing"
    )


    assert active_plan == "max_20x"
    assert plan_credit_usd[active_plan] == 200


def test_real_active_plan_resolves_to_its_authoritative_ceiling_in_tick(tmp_path):
    from ws_b_admission import CreditState

    ceiling, budgets = _real_ceiling_cfg()
    active_plan = ceiling["active_plan"]
    resolved_ceiling = (ceiling["plan_credit_usd"])[active_plan]

    real_budgets = REPO_ROOT / "config" / "budgets.yaml"
    events = tmp_path / "events.jsonl"


    assert lc._monthly_credit_exhausted(real_budgets, events, now=None) is False


    under = CreditState(plan=active_plan, used_usd=resolved_ceiling - 0.01)
    over = CreditState(plan=active_plan, used_usd=resolved_ceiling + 0.01)
    assert lc._monthly_credit_exhausted(real_budgets, events, credit_state=under) is False
    assert lc._monthly_credit_exhausted(real_budgets, events, credit_state=over) is True


def test_budget_regime_is_none_when_no_config_exists(tmp_path):
    assert lc.load_budget_regime(tmp_path / "absent.yaml") is None


def test_malformed_budget_config_raises_rather_than_reading_as_no_budget(tmp_path):
    bad = tmp_path / "budgets.yaml"
    bad.write_text("mustaqil: [this is: not, a: mapping\n", encoding="utf-8")
    with pytest.raises(lc.BudgetConfigError):
        lc.load_budget_regime(bad)


def test_per_day_budget_fails_closed_on_a_malformed_config(tmp_path):
    bad = tmp_path / "budgets.yaml"
    bad.write_text("mustaqil: [this is: not, a: mapping\n", encoding="utf-8")
    assert lc._per_day_budget_exceeded(bad, tmp_path / "events.jsonl") is True


def test_monthly_credit_fails_closed_on_a_malformed_config(tmp_path):
    bad = tmp_path / "budgets.yaml"
    bad.write_text("mustaqil: [this is: not, a: mapping\n", encoding="utf-8")
    assert lc._monthly_credit_exhausted(bad, tmp_path / "events.jsonl") is True


def test_per_day_budget_fails_closed_when_spend_cannot_be_priced(tmp_path):
    budgets = tmp_path / "budgets.yaml"
    budgets.write_text(
        "mustaqil:\n  caps:\n    per_day:\n      max_cost_usd: 5\n", encoding="utf-8"
    )
    events = tmp_path / "events.jsonl"
    events.write_text(
        '{"event_type": "run_end", "run_id": "R1", "model": "sonnet", '
        '"created_at": "2026-07-04T10:10:00Z"}\n',
        encoding="utf-8",
    )
    assert lc._per_day_budget_exceeded(budgets, events) is True


def test_an_empty_event_store_is_zero_spend_not_an_unpriceable_error(tmp_path):
    budgets = tmp_path / "budgets.yaml"
    budgets.write_text(
        "mustaqil:\n  caps:\n    per_day:\n      max_cost_usd: 5\n", encoding="utf-8"
    )
    assert lc._spend_usd_since(tmp_path / "absent.jsonl", budgets, _EPOCH) == 0.0
    assert lc._per_day_budget_exceeded(budgets, tmp_path / "absent.jsonl") is False


_EPOCH = datetime(2026, 1, 1, tzinfo=UTC)
