#!/usr/bin/env python3
"""check_heartbeat_readiness.py — evidence-gated readiness for the HEARTBEAT go-live.

The WS4 HEARTBEAT autonomous-tempo substrate is code-complete, but its live-dispatch
flag ``heartbeat_enabled`` (``config/features.yaml``) defaults OFF. Per ADR-0027 SI-7
and the ORGANISM §5 contract, flipping it to ``true`` is a FOUNDER-ONLY act
(QONUN-5 never-auto-approve) that must not happen on vibes: it requires a **>= 3-day
CLEAN shadow window** — T1 busy_fraction >= 0.60, T2 idle_wave_rate <= 0.15, and T7
quality holding on each day — plus a passing kill-switch drill and zero gate/approval
violations.

This is the read-only, evidence-gated REPORTER for that decision. It inspects the
shadow window (``board/.metrics-history.jsonl``, fed by ``metrics_history_feeder.py``)
and reports, criterion by criterion, whether the bar is met. It NEVER flips the flag,
and it NEVER fabricates readiness — an empty/short/unclean window reports NOT READY,
honestly. The clean-day logic is REUSED from ``loop_controller`` (``day_is_clean`` /
``clean_live_days``) — no forked threshold logic.

Exit codes: 0 = READY (the Founder MAY flip), 1 = NOT READY, 2 = usage/IO error.

This is an OPERATOR / Founder tool. It is deliberately NOT wired as a blocking CI
step: by design the loop is off and this would be permanently red until go-live.

Usage:
    python3 scripts/check_heartbeat_readiness.py
    python3 scripts/check_heartbeat_readiness.py --history board/.metrics-history.jsonl --json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import loop_controller
from _paths import ROOT

try:
    import feature_flags
except ImportError:  # pragma: no cover - environment guard
    feature_flags = None

#: HEARTBEAT go-live needs a shorter, narrower bar than the self-optimizing LADDER
#: (loop_controller.MIN_CLEAN_DAYS = 7, full T1-T5). ADR-0027 / §5 WS4: >= 3 clean days
#: on T1/T2/T7 only. We reuse day_is_clean by neutralising the ladder-only T3/T4/T5
#: (min 0 => always pass), so a "clean day" here means exactly T1 >= 0.60, T2 <= 0.15,
#: T7 holds — no forked threshold logic.
MIN_CLEAN_DAYS_HEARTBEAT = 3
#: ``day_is_clean`` defaults an ABSENT metric to -1 (a fail), so to neutralise the
#: ladder-only T3/T4/T5 we set their mins to -inf (absent or present, always pass).
#: T1 (>=), T2 (<=), and T7 keep their real bars — that is exactly the WS4 window.
HEARTBEAT_TARGETS = {
    "t1_min": 0.60, "t2_max": 0.15,
    "t3_min": float("-inf"), "t4_min": float("-inf"), "t5_min": float("-inf"),
}

DEFAULT_HISTORY = ROOT / "board" / ".metrics-history.jsonl"


def assess(history: list[dict], flag_on: bool) -> dict:
    """Report (never apply) HEARTBEAT go-live readiness. Pure — no I/O, no flip."""
    streak = loop_controller.clean_live_days(history, HEARTBEAT_TARGETS)
    window_met = streak >= MIN_CLEAN_DAYS_HEARTBEAT
    # A clean window is the ONE thing this reporter can verify from evidence. The
    # kill-switch drill + zero-gate-violations are surfaced as Founder-verified gates.
    ready = (not flag_on) and window_met
    blockers: list[str] = []
    if flag_on:
        blockers.append("heartbeat_enabled is ALREADY true — the org is live; nothing to gate")
    if not window_met:
        blockers.append(
            f"insufficient clean shadow window: {streak}/{MIN_CLEAN_DAYS_HEARTBEAT} "
            f"consecutive clean day(s) (T1>=0.60, T2<=0.15, T7 holds)"
        )
    return {
        "ready": ready,
        "heartbeat_enabled": flag_on,
        "clean_days": streak,
        "clean_days_required": MIN_CLEAN_DAYS_HEARTBEAT,
        "window_met": window_met,
        "history_rows": len(history),
        "blockers": blockers,
        # Gates this reporter CANNOT verify — the Founder confirms them before flipping:
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
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--history", type=Path, default=DEFAULT_HISTORY)
    ap.add_argument("--json", action="store_true", help="emit the report as JSON")
    args = ap.parse_args(argv)

    history = loop_controller._load_jsonl(args.history)
    flag_on = bool(feature_flags.enabled("heartbeat_enabled")) if feature_flags else False
    report = assess(history, flag_on)

    print(json.dumps(report, indent=2) if args.json else _render(report))
    return 0 if report["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
