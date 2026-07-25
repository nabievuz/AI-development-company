#!/usr/bin/env python3
"""tests/test_loop_controller.py — self-optimization loop promotion controller (RFC-001 §5).

The load-bearing safety properties: promotions never skip a rung, require >=1 week
clean live evidence AND a human-approved GATE-6 record, and the controller NEVER
mutates loop.yaml (it only reports / drafts).
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import loop_controller as lc  # noqa: E402  (import after path manipulation)

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


# --------------------------------------------------------------------------- #
# Ladder — one rung at a time, never skip
# --------------------------------------------------------------------------- #

def test_ladder_one_rung():
    assert lc.next_mode("shadow") == "measured"
    assert lc.next_mode("measured") == "limited_live"
    assert lc.next_mode("limited_live") == "full"
    assert lc.next_mode("full") is None
    assert lc.next_mode("bogus") is None


# --------------------------------------------------------------------------- #
# Clean-live-days evidence
# --------------------------------------------------------------------------- #

def test_clean_days_counts_trailing_streak():
    history = [{"t1": 0.1, "t7_holds": False}] + [_clean_day() for _ in range(7)]
    assert lc.clean_live_days(history, T) == 7


def test_a_bad_day_breaks_the_streak():
    history = [_clean_day() for _ in range(5)] + [{"t1": 0.1, "t7_holds": False}] + [_clean_day() for _ in range(2)]
    assert lc.clean_live_days(history, T) == 2  # only the trailing clean days


def test_day_not_clean_if_t7_drops():
    day = dict(_clean_day(), t7_holds=False)
    assert lc.day_is_clean(day, T) is False


# --------------------------------------------------------------------------- #
# Approved promotion record
# --------------------------------------------------------------------------- #

def test_approved_record_required():
    assert lc.has_approved_promotion_record([_approved_record()], "shadow", "measured") is True


def test_unapproved_record_does_not_count():
    rec = _approved_record(approver="")  # no human sign-off
    assert lc.has_approved_promotion_record([rec], "shadow", "measured") is False


def test_wrong_rung_record_does_not_count():
    assert lc.has_approved_promotion_record([_approved_record(to="full")], "shadow", "measured") is False


# --------------------------------------------------------------------------- #
# evaluate_promotion — the safety gate
# --------------------------------------------------------------------------- #

def test_not_eligible_with_no_evidence():
    r = lc.evaluate_promotion("shadow", [], [], T)
    assert r["eligible"] is False
    assert len(r["blockers"]) == 2  # insufficient evidence + no approved record


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


# --------------------------------------------------------------------------- #
# Draft is unapproved; controller never mutates
# --------------------------------------------------------------------------- #

def test_promotion_draft_is_unapproved():
    rec = lc.promotion_draft("shadow", "measured", "2026-06-22T00:00:00Z")["gate_6_record"]
    assert rec["approval"]["approved_by"] == ""
    assert rec["guardrails"]["max_quality_drop"] == 0
    assert rec["rollout"]["mode"] == "shadow"


def test_cli_inert_loop_stays_shadow():
    # real shadow config + no live data -> not eligible -> exit 0, loop unchanged
    assert lc.main([]) == 0


def test_cli_does_not_mutate_loop_config():
    before = (REPO_ROOT / "config" / "loop.yaml").read_text()
    lc.main(["--propose"])
    assert (REPO_ROOT / "config" / "loop.yaml").read_text() == before  # never mutated


# --------------------------------------------------------------------------- #
# Robustness hardening (review nits)
# --------------------------------------------------------------------------- #

def test_whitespace_approver_rejected():
    assert lc.has_approved_promotion_record([_approved_record(approver="   ")], "shadow", "measured") is False


def test_day_is_clean_non_dict_is_false():
    assert lc.day_is_clean(None, T) is False
    assert lc.clean_live_days([None, "x"], T) == 0


# --------------------------------------------------------------------------- #
# G1 — monthly credit ceiling adapter (FR-004, DAS-1618 / design §3.3)
# --------------------------------------------------------------------------- #


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
    # No active_plan -> inert here (never a fabricated pause; §3.5 makes the
    # undeclared plan a readiness blocker instead, not a tick freeze).
    budgets = _write_budgets(tmp_path, active_plan=None)
    assert lc._monthly_credit_exhausted(budgets, tmp_path / "events.jsonl") is False


def test_monthly_credit_exhausted_false_when_budgets_missing(tmp_path):
    assert lc._monthly_credit_exhausted(tmp_path / "nope.yaml", tmp_path / "events.jsonl") is False


def test_monthly_credit_exhausted_with_explicit_credit_state_exhausted(tmp_path):
    import ws_b_admission as wba

    budgets = _write_budgets(tmp_path, active_plan="pro")
    state = wba.CreditState(plan="pro", used_usd=20.0)  # >= 20 limit
    assert lc._monthly_credit_exhausted(budgets, tmp_path / "events.jsonl", credit_state=state) is True


def test_monthly_credit_exhausted_with_explicit_credit_state_not_exhausted(tmp_path):
    import ws_b_admission as wba

    budgets = _write_budgets(tmp_path, active_plan="pro")
    state = wba.CreditState(plan="pro", used_usd=1.0)
    assert lc._monthly_credit_exhausted(budgets, tmp_path / "events.jsonl", credit_state=state) is False


def test_monthly_credit_exhausted_does_not_inherit_max_20x_default(tmp_path):
    # Even though CreditState()'s dataclass default plan is max_20x (the most
    # generous), an undeclared active_plan must never silently borrow it.
    budgets = _write_budgets(tmp_path, active_plan=None)
    assert lc._monthly_credit_exhausted(budgets, tmp_path / "events.jsonl") is False


def test_tick_surfaces_monthly_credit_exhausted_rail(tmp_path):
    budgets = _write_budgets(tmp_path, active_plan=None)
    r = lc.tick(budgets_path=budgets, metrics_history=tmp_path / "nope.jsonl",
                events_path=tmp_path / "events.jsonl")
    assert "monthly_credit_exhausted" in r["safety_rails"]
    assert r["safety_rails"]["monthly_credit_exhausted"] is False


def test_tick_never_calls_admit_or_gated_admit(monkeypatch, tmp_path):
    """The tick path must reuse the two pure functions directly — never admit()
    (fails closed on absent model) or gated_admit() (gated on a different flag)."""
    import ws_b_admission as wba

    def _boom(*a, **k):
        raise AssertionError("tick must not call admit()/gated_admit()")

    monkeypatch.setattr(wba, "admit", _boom)
    monkeypatch.setattr(wba, "gated_admit", _boom)
    budgets = _write_budgets(tmp_path, active_plan="pro")
    r = lc.tick(budgets_path=budgets, metrics_history=tmp_path / "nope.jsonl",
                events_path=tmp_path / "events.jsonl")
    assert r["safety_rails"]["monthly_credit_exhausted"] in (True, False)


# --------------------------------------------------------------------------- #
# D1/DAS-1618 fix — used_usd derived from a WINDOWED (month-to-date) ledger,
# not a lifetime one. The reviewer's bounce: a lifetime total is monotonic
# and never resets at the billing-cycle boundary, so once crossed it latches
# the ceiling permanently on. THE load-bearing assertion: spend from a
# PREVIOUS billing month must not count toward the current month's ceiling.
# --------------------------------------------------------------------------- #

import datetime as _dt  # noqa: E402
import json as _json  # noqa: E402


def _write_budgets_with_pricing(tmp_path, *, active_plan=None, plan_credit_usd=None):
    """Like _write_budgets, but also carries tier pricing so aggregate_spans
    (invoked internally, without an injected credit_state) can price spans."""
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
    """Reproduces the reviewer's exact scenario: an event store containing
    ONLY spend from a previous billing month (2025-01), enough to blow a
    lifetime total past a $20 plan cap, evaluated as of "now" = 2026-07-24.

    A lifetime-aggregate implementation (the pre-fix code, D1) would return
    True here (110.0 lifetime >= 20). The fixed implementation must return
    False: zero spend has occurred in the CURRENT billing month.
    """
    budgets = _write_budgets_with_pricing(tmp_path, active_plan="pro")
    events = tmp_path / "events.jsonl"
    # ~110 USD of opus spend, entirely in January 2025 (a prior billing month).
    _write_span_events(events, [("2025-01-15T12:00:00Z", 10_000_000, 3_000_000)])

    # Sanity check: lifetime aggregation genuinely does see this spend (proves
    # the fixture reproduces the reviewer's premise, not a vacuous test).
    scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    from cost.cost_ledger import aggregate_spans  # noqa: PLC0415
    lifetime_ledger = aggregate_spans(events, budgets)
    assert lifetime_ledger is not None
    assert lifetime_ledger.raw_estimated_cost_usd >= 20.0  # would have exhausted a $20 cap

    now = _dt.datetime(2026, 7, 24, 12, 0, 0, tzinfo=_dt.UTC)
    assert lc._monthly_credit_exhausted(budgets, events, now=now) is False


def test_monthly_credit_exhausted_true_when_spend_is_in_current_month(tmp_path):
    """Positive control: spend that genuinely falls inside the current
    billing month DOES exhaust the ceiling — the window isn't just excluding
    everything."""
    budgets = _write_budgets_with_pricing(tmp_path, active_plan="pro")
    events = tmp_path / "events.jsonl"
    _write_span_events(events, [("2026-07-10T09:00:00Z", 10_000_000, 3_000_000)])

    now = _dt.datetime(2026, 7, 24, 12, 0, 0, tzinfo=_dt.UTC)
    assert lc._monthly_credit_exhausted(budgets, events, now=now) is True


def test_monthly_credit_exhausted_mixed_months_only_current_counts(tmp_path):
    """Mixed store: previous-month spend alone would exhaust the cap, but the
    small in-window spend does not — proving prior-period spend is excluded
    rather than merely diluted."""
    budgets = _write_budgets_with_pricing(tmp_path, active_plan="pro")
    events = tmp_path / "events.jsonl"
    _write_span_events(events, [
        ("2025-01-15T12:00:00Z", 10_000_000, 3_000_000),  # prior month, ~$110 alone
        ("2026-07-05T08:00:00Z", 100, 50),                  # this month, a few cents
    ])

    now = _dt.datetime(2026, 7, 24, 12, 0, 0, tzinfo=_dt.UTC)
    assert lc._monthly_credit_exhausted(budgets, events, now=now) is False


# --------------------------------------------------------------------------- #
# D-per-day/DAS-1632 fix — _per_day_budget_exceeded's ledger read is now
# WINDOWED (day-to-date), not lifetime. Same defect shape as D1/DAS-1618: a
# lifetime total is monotonic and never resets at the day boundary, so once
# crossed it latches the SI-5 per-day rail on forever. THE load-bearing
# assertion: spend from a PREVIOUS UTC calendar day must not count toward
# today's cap.
# --------------------------------------------------------------------------- #

def _write_per_day_budgets_with_pricing(tmp_path, *, max_cost_usd):
    """DAS-1639: the per-day rail (`_per_day_budget_exceeded`) reads
    `mustaqil.caps.per_day.max_cost_usd` — the MUSTAQIL SI-5 ceiling — NOT the
    top-level `caps.per_day` block, which `config/budgets.yaml` documents as
    informational-only. Writing the cap under `mustaqil.caps.per_day` here (and
    NOT under the top-level `caps:` block) is itself load-bearing: if the rail
    ever silently re-points at the informational block, these tests fail loudly
    because the top-level block carries no cap at all."""
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
    """DAS-1639 pin. `_per_day_budget_exceeded` MUST resolve its cap from
    `mustaqil.caps.per_day.max_cost_usd` (the MUSTAQIL SI-5 self-imposed
    ceiling), never from the top-level `caps.per_day.max_cost_usd` (the
    org-wide block `config/budgets.yaml` itself documents as
    "informational — not a blocking gate until C1 is promoted").

    This is deliberately NOT a bare `== 15.0` assertion — that would keep
    passing if someone later moved $15 into the wrong block. Instead the
    fixture sets the two blocks to CONTRADICTORY values: a top-level cap high
    enough that today's spend would NOT breach it, and a `mustaqil` cap low
    enough that the SAME spend DOES breach it. If a future rename or reshuffle
    of budgets.yaml silently re-points the rail at the org block, this flips
    from True to False and fails loudly instead of quietly re-widening the
    rail back toward $500.
    """
    lines = [
        "caps:",
        "  per_day:",
        "    max_cost_usd: 500.00",   # org-informational block: would NOT breach
        "mustaqil:",
        "  caps:",
        "    per_day:",
        "      max_cost_usd: 15.00",  # SI-5 authoritative block: DOES breach
        "tiers:",
        "  opus:",
        "    input_per_1m: 5.00",
        "    cached_input_per_1m: 0.50",
        "    output_per_1m: 25.00",
    ]
    budgets = tmp_path / "budgets.yaml"
    budgets.write_text("\n".join(lines) + "\n", encoding="utf-8")

    events = tmp_path / "events.jsonl"
    # ~$20 of opus spend today: over the $15 mustaqil cap, under the $500 org cap.
    _write_span_events(events, [("2026-07-24T09:00:00Z", 4_000_000, 0)])

    now = _dt.datetime(2026, 7, 24, 12, 0, 0, tzinfo=_dt.UTC)
    assert lc._per_day_budget_exceeded(budgets, events, now=now) is True, (
        "rail did not resolve mustaqil.caps.per_day.max_cost_usd — it must "
        "breach at $20 spend against the $15 SI-5 ceiling even though the "
        "$500 org-informational ceiling is untouched"
    )


def test_per_day_budget_reproduces_defect_before_fix_would_have_been_true(tmp_path):
    """Reproduces the SRE Lead's exact scenario for the per-day sibling of D1:
    an event store containing ONLY spend from a previous UTC calendar day,
    enough to blow a lifetime total past a $20 daily cap, evaluated as of
    "now" = 2026-07-24.

    A lifetime-aggregate implementation (the pre-fix code) would return True
    here (110.0 lifetime >= 20). The fixed implementation must return False:
    zero spend has occurred in the CURRENT UTC calendar day.
    """
    budgets = _write_per_day_budgets_with_pricing(tmp_path, max_cost_usd=20)
    events = tmp_path / "events.jsonl"
    # ~110 USD of opus spend, entirely on the previous UTC day.
    _write_span_events(events, [("2026-07-23T12:00:00Z", 10_000_000, 3_000_000)])

    # Sanity check: lifetime aggregation genuinely does see this spend (proves
    # the fixture reproduces the premise, not a vacuous test).
    scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    from cost.cost_ledger import aggregate_spans  # noqa: PLC0415
    lifetime_ledger = aggregate_spans(events, budgets)
    assert lifetime_ledger is not None
    assert lifetime_ledger.raw_estimated_cost_usd >= 20.0  # would have exceeded a $20 daily cap

    now = _dt.datetime(2026, 7, 24, 12, 0, 0, tzinfo=_dt.UTC)
    assert lc._per_day_budget_exceeded(budgets, events, now=now) is False


def test_per_day_budget_true_when_spend_is_today(tmp_path):
    """Positive control: spend that genuinely falls inside the current UTC
    day DOES trip the cap — the window isn't just excluding everything."""
    budgets = _write_per_day_budgets_with_pricing(tmp_path, max_cost_usd=20)
    events = tmp_path / "events.jsonl"
    _write_span_events(events, [("2026-07-24T09:00:00Z", 10_000_000, 3_000_000)])

    now = _dt.datetime(2026, 7, 24, 12, 0, 0, tzinfo=_dt.UTC)
    assert lc._per_day_budget_exceeded(budgets, events, now=now) is True


def test_per_day_budget_mixed_days_only_today_counts(tmp_path):
    """Mixed store: previous-day spend alone would exceed the cap, but the
    small in-window spend does not — proving prior-day spend is excluded
    rather than merely diluted."""
    budgets = _write_per_day_budgets_with_pricing(tmp_path, max_cost_usd=20)
    events = tmp_path / "events.jsonl"
    _write_span_events(events, [
        ("2026-07-23T12:00:00Z", 10_000_000, 3_000_000),  # prior day, ~$110 alone
        ("2026-07-24T08:00:00Z", 100, 50),                 # today, a few cents
    ])

    now = _dt.datetime(2026, 7, 24, 12, 0, 0, tzinfo=_dt.UTC)
    assert lc._per_day_budget_exceeded(budgets, events, now=now) is False


def test_per_day_budget_boundary_instant_is_included(tmp_path):
    """A span at exactly the window start (00:00:00 UTC of today) must be
    INCLUDED, not excluded — the shipped comparison is `ts < since -> skip`
    (i.e. >=, boundary included). Mutation testing found no test pinned this
    for the per-day path; this is the one requested alongside the month one."""
    budgets = _write_per_day_budgets_with_pricing(tmp_path, max_cost_usd=1)
    events = tmp_path / "events.jsonl"
    # Small spend exactly at 00:00:00 UTC of "today" — must count toward today.
    _write_span_events(events, [("2026-07-24T00:00:00Z", 100_000, 30_000)])

    now = _dt.datetime(2026, 7, 24, 12, 0, 0, tzinfo=_dt.UTC)
    scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    from cost.cost_ledger import aggregate_spans  # noqa: PLC0415
    day_start = lc._window_start(now, unit="day")
    windowed_ledger = aggregate_spans(events, budgets, since=day_start)
    assert windowed_ledger is not None  # boundary span was NOT excluded
    assert windowed_ledger.raw_estimated_cost_usd > 0


def test_monthly_credit_boundary_instant_is_included(tmp_path):
    """Sibling boundary test for the month window (D1/DAS-1618): a span at
    exactly the window start (the 1st of the month, 00:00:00 UTC) must be
    INCLUDED. Mutation testing flagged this exact-boundary case as missing."""
    budgets = _write_budgets_with_pricing(tmp_path, active_plan="pro")
    events = tmp_path / "events.jsonl"
    _write_span_events(events, [("2026-07-01T00:00:00Z", 10_000_000, 3_000_000)])

    now = _dt.datetime(2026, 7, 24, 12, 0, 0, tzinfo=_dt.UTC)
    # A boundary spend big enough to exhaust the $20 "pro" cap proves it
    # WAS counted (excluded would read used_usd=0, never exhausting).
    assert lc._monthly_credit_exhausted(budgets, events, now=now) is True


def test_tick_threads_now_once_into_per_day_budget(monkeypatch, tmp_path):
    """tick() must resolve `_now` ONCE and thread it into
    _per_day_budget_exceeded — not read the clock a second time inside the
    helper. Proven by injecting a distinguishable `now` via tick() and
    asserting the per-day helper receives that exact instant."""
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
    (exp / "bad.yaml").mkdir()  # a directory named like a record -> read raises OSError
    assert lc._load_records(exp) == []
    rc = lc.main(["--loop-config", str(REPO_ROOT / "config" / "loop.yaml"),
                  "--experiments", str(exp), "--metrics-history", str(tmp_path / "nope.jsonl")])
    assert rc == 0


# --------------------------------------------------------------------------- #
# DAS-1634 — SI-5/FR-004 alert limb: a budget-rail trip must be AUDIBLE,
# routed through the EXISTING alerting.py machinery, WITHOUT ever changing
# the tempo decision (idle stays idle for the same reason; DECISIONS stays
# the closed {dispatch, validate, idle} alphabet).
# --------------------------------------------------------------------------- #


def test_tick_no_alert_on_a_normal_tick(tmp_path):
    """Both rails cold -> tick()'s alert must be None (no crying wolf)."""
    r = lc.tick(metrics_history=tmp_path / "nope.jsonl", events_path=tmp_path / "events.jsonl")
    assert r["safety_rails"]["per_day_budget_exceeded"] is False
    assert r["safety_rails"]["monthly_credit_exhausted"] is False
    assert r["alert"] is None


def test_tick_emits_alert_on_per_day_trip(tmp_path):
    """A per-day cap trip (DAS-1640-windowed, non-latching) must emit a
    sanctioned_pause alert through alerting.sanctioned_pause_alert — via the
    SAME dict shape (severity/metric/message) evaluate_alerts() produces."""
    budgets = _write_per_day_budgets_with_pricing(tmp_path, max_cost_usd=1)
    events = tmp_path / "events.jsonl"
    _write_span_events(events, [("2026-07-24T09:00:00Z", 10_000_000, 3_000_000)])  # ~$65, today

    now = _dt.datetime(2026, 7, 24, 12, 0, 0, tzinfo=_dt.UTC)
    r = lc.tick(budgets_path=budgets, metrics_history=tmp_path / "nope.jsonl", events_path=events, now=now)
    assert r["safety_rails"]["per_day_budget_exceeded"] is True
    assert r["alert"] is not None
    assert r["alert"]["severity"] == "info"
    assert r["alert"]["metric"] == "SI-5"
    assert "per-day budget cap" in r["alert"]["message"]
    # A sanctioned pause must read as HEALTHY, never a critical breach.
    assert r["alert"]["severity"] != "critical"


def test_tick_emits_alert_on_monthly_trip(tmp_path):
    """A monthly credit-ceiling exhaustion must also emit a sanctioned_pause
    alert — same mechanism, distinguishable message from the per-day trip."""
    budgets = _write_budgets_with_pricing(tmp_path, active_plan="pro")
    events = tmp_path / "events.jsonl"
    _write_span_events(events, [("2026-07-10T09:00:00Z", 10_000_000, 3_000_000)])  # this month, ~$65 > $20 cap

    now = _dt.datetime(2026, 7, 24, 12, 0, 0, tzinfo=_dt.UTC)
    r = lc.tick(budgets_path=budgets, metrics_history=tmp_path / "nope.jsonl", events_path=events, now=now)
    assert r["safety_rails"]["monthly_credit_exhausted"] is True
    assert r["alert"] is not None
    assert r["alert"]["severity"] == "info"
    assert r["alert"]["metric"] == "SI-5"
    assert "monthly credit ceiling" in r["alert"]["message"]


def test_alert_wiring_does_not_change_the_decision(tmp_path):
    """BYTE-IDENTICAL DISPATCH PROOF: the same tick inputs, run once with the
    alert wiring present (normal `lc.tick`) and once with `alerting` import
    forced to fail (simulating the wiring being absent), must produce the
    EXACT same `decision` dict. The alert changes observability only."""
    budgets = _write_per_day_budgets_with_pricing(tmp_path, max_cost_usd=1)
    events = tmp_path / "events.jsonl"
    _write_span_events(events, [("2026-07-24T09:00:00Z", 10_000_000, 3_000_000)])
    now = _dt.datetime(2026, 7, 24, 12, 0, 0, tzinfo=_dt.UTC)

    with_alert = lc.tick(budgets_path=budgets, metrics_history=tmp_path / "nope.jsonl",
                          events_path=events, now=now)
    assert with_alert["alert"] is not None  # sanity: the wiring actually fired

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

    assert without_alert["alert"] is None  # wiring absent -> no alert, as designed
    # The load-bearing assertion: decision + every safety rail are BYTE-IDENTICAL.
    assert without_alert["decision"] == with_alert["decision"]
    assert without_alert["safety_rails"] == with_alert["safety_rails"]
    assert without_alert["promotion"] == with_alert["promotion"]
    assert without_alert["mode"] == with_alert["mode"]


def test_sanctioned_pause_alert_severity_distinct_from_critical_cost_breach():
    """The design-tension resolution, proven directly: alerting.py's OWN
    critical COST alert (budget_governor breach) and the SI-5 sanctioned
    pause alert must never collapse to the same severity — otherwise a
    healthy ceiling-hit and a real emergency are indistinguishable and
    filter_quiet cannot tell them apart."""
    import alerting as al

    sanctioned = al.sanctioned_pause_alert(True, False)
    assert sanctioned["severity"] == "info"

    cost_breach = al.evaluate_alerts(
        {"per_day_cost_usd": 100.0},
        thresholds={},
        budgets={"caps": {"per_day": {"max_cost_usd": 10.0}}},
    )
    assert any(a["severity"] == "critical" and a["metric"] == "COST" for a in cost_breach)

    # filter_quiet: the sanctioned pause is NOT an anomaly (stays out of Quiet
    # Mode / --fail-on-critical); the cost breach IS.
    assert al.filter_quiet([sanctioned]) == []
    assert al.filter_quiet(cost_breach) == cost_breach


def test_sanctioned_pause_alert_none_when_both_rails_cold():
    import alerting as al

    assert al.sanctioned_pause_alert(False, False) is None


def test_flow_router_decisions_closed_alphabet_unchanged():
    """Mechanical assertion (ADR-0042 SI-5.3): the alert limb must not add a
    fourth decision — DECISIONS stays exactly {dispatch, validate, idle}."""
    import flow_router

    assert frozenset({"dispatch", "validate", "idle"}) == flow_router.DECISIONS


# --------------------------------------------------------------------------- #
# DAS-1629 — the REAL config/budgets.yaml now DECLARES active_plan (Founder
# decision 2026-07-25: max_20x). These tests pin that the declared plan
# resolves to its AUTHORITATIVE per-plan ceiling in the tick path — asserting
# against `plan_credit_usd[active_plan]`, never a bare `== 200`, so that a
# future plan change or a plan/value mis-declaration (200 moved to the wrong
# key) is caught rather than silently passing.
# --------------------------------------------------------------------------- #

def _real_ceiling_cfg():
    from ws_b_admission import load_mustaqil_budgets  # noqa: PLC0415

    budgets = load_mustaqil_budgets(REPO_ROOT / "config" / "budgets.yaml")
    return (budgets.get("monthly_credit_ceiling") or {}), budgets


def test_real_budgets_declares_a_resolvable_active_plan():
    """The blocker DAS-1629 closes: active_plan must be declared AND resolve to
    a real key in plan_credit_usd (a mis-declared plan resolves to nothing and
    would leave the ceiling unenforceable)."""
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
    # Founder decision of record (2026-07-25): max_20x -> $200/mo. Derived from
    # the authoritative key, so if $200 were moved off max_20x this fails loudly.
    assert active_plan == "max_20x"
    assert plan_credit_usd[active_plan] == 200


def test_real_active_plan_resolves_to_its_authoritative_ceiling_in_tick(tmp_path):
    """End-to-end: `_monthly_credit_exhausted` reads the REAL budgets and
    enforces exactly `plan_credit_usd[active_plan]` — proven by the boundary,
    not a hardcoded number. Spend a cent under the resolved ceiling is NOT
    exhausted; a cent over IS. Events live in tmp_path — the real
    board/.events.jsonl is never touched."""
    from ws_b_admission import CreditState  # noqa: PLC0415

    ceiling, budgets = _real_ceiling_cfg()
    active_plan = ceiling["active_plan"]
    resolved_ceiling = (ceiling["plan_credit_usd"])[active_plan]

    real_budgets = REPO_ROOT / "config" / "budgets.yaml"
    events = tmp_path / "events.jsonl"  # absent -> $0 month-to-date

    # $0 spend -> the tick EVALUATES the ceiling (not inert) and is under it.
    assert lc._monthly_credit_exhausted(real_budgets, events, now=None) is False

    # Boundary via an injected CreditState keyed on the REAL declared plan:
    under = CreditState(plan=active_plan, used_usd=resolved_ceiling - 0.01)
    over = CreditState(plan=active_plan, used_usd=resolved_ceiling + 0.01)
    assert lc._monthly_credit_exhausted(real_budgets, events, credit_state=under) is False
    assert lc._monthly_credit_exhausted(real_budgets, events, credit_state=over) is True
