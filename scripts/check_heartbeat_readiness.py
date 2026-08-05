#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path

import loop_controller
import yaml
from _paths import ROOT

try:
    import feature_flags
except ImportError:
    feature_flags = None


MIN_CLEAN_DAYS_HEARTBEAT = 3


HEARTBEAT_TARGETS = {
    "t1_min": 0.60, "t2_max": 0.15,
    "t3_min": float("-inf"), "t4_min": float("-inf"), "t5_min": float("-inf"),
}

DEFAULT_HISTORY = ROOT / "board" / ".metrics-history.jsonl"
DEFAULT_BUDGETS = ROOT / "config" / "budgets.yaml"
DEFAULT_EVENTS = ROOT / "board" / ".events.jsonl"


def _active_plan(budgets_path: Path) -> str | None:
    try:
        data = yaml.safe_load(budgets_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    ceiling = (data.get("mustaqil") or {}).get("monthly_credit_ceiling") or {}
    plan = ceiling.get("active_plan")
    return plan.strip() if isinstance(plan, str) and plan.strip() else None


def assess(
    history: list[dict],
    flag_on: bool,
    *,
    active_plan: str | None = None,
    credit_exhausted: bool = False,
) -> dict:
    streak = loop_controller.clean_live_days(history, HEARTBEAT_TARGETS)
    window_met = streak >= MIN_CLEAN_DAYS_HEARTBEAT
    credit_declared = isinstance(active_plan, str) and bool(active_plan.strip())
    credit_precondition_met = credit_declared and not credit_exhausted


    ready = (not flag_on) and window_met and credit_precondition_met
    blockers: list[str] = []
    if flag_on:
        blockers.append("heartbeat_enabled is ALREADY true — the org is live; nothing to gate")
    if not window_met:
        blockers.append(
            f"insufficient clean shadow window: {streak}/{MIN_CLEAN_DAYS_HEARTBEAT} "
            f"consecutive clean day(s) (T1>=0.60, T2<=0.15, T7 holds)"
        )
    if not credit_declared:
        blockers.append(
            "monthly credit ceiling not enforceable: "
            "mustaqil.monthly_credit_ceiling.active_plan is undeclared"
        )
    elif credit_exhausted:
        blockers.append("monthly subscription credit exhausted — sanctioned pause in effect")
    return {
        "ready": ready,
        "heartbeat_enabled": flag_on,
        "clean_days": streak,
        "clean_days_required": MIN_CLEAN_DAYS_HEARTBEAT,
        "window_met": window_met,
        "history_rows": len(history),
        "active_plan": active_plan,
        "credit_ceiling_enforceable": credit_declared,
        "credit_exhausted": credit_exhausted,
        "blockers": blockers,

        "founder_verified_gates": [
            "kill-switch drill passes: python3 scripts/kill_switch_drill.py --smoke",
            "zero gate/approval violations in the event log (check_never_auto_approve + interrupts answered)",
        ],
    }


def _render(report: dict) -> str:
    lines = ["HEARTBEAT go-live readiness (ADR-0027 SI-7 / §5 WS4) — evidence-gated report", "=" * 74]
    flag = "true (LIVE)" if report["heartbeat_enabled"] else "false (shadow)"
    lines.append(f"  heartbeat_enabled ........ {flag}")
    mark = "OK " if report["window_met"] else "XX "
    lines.append(
        f"  {mark}clean shadow window ..... {report['clean_days']}/{report['clean_days_required']} "
        f"consecutive clean day(s)  (from {report['history_rows']} history row(s))"
    )
    credit_mark = "OK " if (report["credit_ceiling_enforceable"] and not report["credit_exhausted"]) else "XX "
    plan_desc = report["active_plan"] or "undeclared"
    lines.append(
        f"  {credit_mark}monthly credit ceiling .. plan={plan_desc}  "
        f"exhausted={report['credit_exhausted']}  (FR-004)"
    )
    lines.append("  Founder-verified gates (this tool cannot check — confirm before flipping):")
    for g in report["founder_verified_gates"]:
        lines.append(f"    - {g}")
    lines.append("-" * 74)
    if report["ready"]:
        lines.append(
            "  VERDICT: READY — the >=3-day clean shadow window is met. The Founder MAY now\n"
            "  flip heartbeat_enabled: true in config/features.yaml (QONUN-5 never-auto-approve\n"
            "  — a human act), after confirming the Founder-verified gates above."
        )
    else:
        lines.append("  VERDICT: NOT READY. Blockers:")
        for b in report["blockers"]:
            lines.append(f"    - {b}")
        lines.append(
            "  Next: keep the scheduler in shadow (heartbeat_enabled: false) collecting\n"
            "  counted waves; feed daily rows with metrics_history_feeder.py; re-run this check."
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description='check_heartbeat_readiness.py — evidence-gated readiness for the HEARTBEAT go-live.')
    ap.add_argument("--history", type=Path, default=DEFAULT_HISTORY)
    ap.add_argument("--budgets", type=Path, default=DEFAULT_BUDGETS,
                    help="path to config/budgets.yaml (FR-004 monthly credit ceiling)")
    ap.add_argument("--events", type=Path, default=DEFAULT_EVENTS,
                    help="path to the JSONL event store (month-to-date credit usage)")
    ap.add_argument("--json", action="store_true", help="emit the report as JSON")
    args = ap.parse_args(argv)

    history = loop_controller._load_jsonl(args.history)
    flag_on = bool(feature_flags.enabled("heartbeat_enabled")) if feature_flags else False
    active_plan = _active_plan(args.budgets)
    credit_exhausted = (
        loop_controller._monthly_credit_exhausted(args.budgets, args.events)
        if active_plan
        else False
    )
    report = assess(history, flag_on, active_plan=active_plan, credit_exhausted=credit_exhausted)

    print(json.dumps(report, indent=2) if args.json else _render(report))
    return 0 if report["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
