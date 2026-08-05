#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any


DISPATCH = "dispatch"
VALIDATE = "validate"
IDLE = "idle"


DECISIONS: frozenset[str] = frozenset({DISPATCH, VALIDATE, IDLE})


TICKET_CREATED = "ticket_created"
WAVE_COMPLETED = "wave_completed"
INTERRUPT_ANSWERED = "interrupt_answered"
AFTER_N_RUNS = "after_n_runs"
CRON_TICK = "cron_tick"


TRIGGERS: frozenset[str] = frozenset(
    {TICKET_CREATED, WAVE_COMPLETED, INTERRUPT_ANSWERED, AFTER_N_RUNS, CRON_TICK}
)


DEFAULT_CHECKPOINT_EVERY = 10


MAX_CONCURRENT_WAVES = 1


@dataclass(frozen=True)
class Decision:

    action: str
    trigger: str
    reason: str

    def as_dict(self) -> dict[str, str]:
        return {"action": self.action, "trigger": self.trigger, "reason": self.reason}


@dataclass(frozen=True)
class TickContext:

    trigger: str
    events: Sequence[dict[str, Any]] = field(default_factory=tuple)
    checkpoint_every: int = DEFAULT_CHECKPOINT_EVERY
    max_concurrent_waves: int = MAX_CONCURRENT_WAVES
    pending_work: bool = False
    in_quiet_hours: bool = False
    break_glass_active: bool = False
    per_day_budget_exceeded: bool = False
    monthly_credit_exhausted: bool = False


def _runs_in_flight(events: Sequence[dict[str, Any]]) -> set[str]:
    started: set[str] = set()
    ended: set[str] = set()
    for ev in events:
        if not isinstance(ev, dict):
            continue
        rid = ev.get("run_id")
        if not isinstance(rid, str) or not rid:
            continue
        et = ev.get("event_type")
        if et == "run_start":
            started.add(rid)
        elif et == "run_end":
            ended.add(rid)
    return started - ended


def _completed_run_count(events: Sequence[dict[str, Any]]) -> int:
    return sum(
        1
        for ev in events
        if isinstance(ev, dict) and ev.get("event_type") == "run_end"
    )


def _wave_in_flight(ctx: TickContext) -> bool:
    return len(_runs_in_flight(ctx.events)) >= ctx.max_concurrent_waves


def _dispatch_blocked(ctx: TickContext) -> tuple[bool, str]:
    if ctx.break_glass_active:
        return True, "break-glass override active (SI-3)"
    if ctx.in_quiet_hours:
        return True, "inside quiet-hours window (SI-4)"
    if ctx.per_day_budget_exceeded:
        return True, "per-day budget cap already breached (SI-5)"
    if ctx.monthly_credit_exhausted:
        return True, "monthly subscription credit exhausted — sanctioned pause (SI-5/FR-004)"
    if _wave_in_flight(ctx):
        return True, "a wave is already in flight, max 1 (SI-6)"
    return False, ""


def _on_ticket_created(ctx: TickContext) -> tuple[str, str]:
    return DISPATCH, "ticket_created: new work exists — dispatch the next wave"


def _on_wave_completed(ctx: TickContext) -> tuple[str, str]:
    return VALIDATE, "wave_completed: run validators, then decide the next tick"


def _on_interrupt_answered(ctx: TickContext) -> tuple[str, str]:
    return (
        DISPATCH,
        "interrupt_answered: human wrote resume — dispatch to resume "
        "(router never auto-answers, SI-7)",
    )


def _on_after_n_runs(ctx: TickContext) -> tuple[str, str]:
    n = _completed_run_count(ctx.events)
    every = ctx.checkpoint_every
    if every > 0 and n > 0 and n % every == 0:
        return VALIDATE, f"after_n_runs: {n} runs completed (multiple of {every}) — validate checkpoint"
    return IDLE, f"after_n_runs: {n} runs completed — no checkpoint due"


def _on_cron_tick(ctx: TickContext) -> tuple[str, str]:
    if ctx.pending_work:
        return DISPATCH, "cron_tick: pending board work — dispatch the next wave"
    n = _completed_run_count(ctx.events)
    every = ctx.checkpoint_every
    if every > 0 and n > 0 and n % every == 0:
        return VALIDATE, f"cron_tick: {n} runs completed (multiple of {every}) — validate checkpoint"
    return IDLE, "cron_tick: nothing pending, no checkpoint due — idle"


_HANDLERS: dict[str, Callable[[TickContext], tuple[str, str]]] = {
    TICKET_CREATED: _on_ticket_created,
    WAVE_COMPLETED: _on_wave_completed,
    INTERRUPT_ANSWERED: _on_interrupt_answered,
    AFTER_N_RUNS: _on_after_n_runs,
    CRON_TICK: _on_cron_tick,
}


def route(ctx: TickContext) -> Decision:
    trigger = ctx.trigger
    handler = _HANDLERS.get(trigger)
    if handler is None:
        return Decision(IDLE, str(trigger), f"unknown trigger {trigger!r} — degraded to idle")

    try:
        action, reason = handler(ctx)
    except Exception as exc:
        return Decision(IDLE, trigger, f"handler error degraded to idle: {exc!r}")

    if action not in DECISIONS:
        return Decision(IDLE, trigger, f"handler returned non-decision {action!r} — degraded to idle")

    if action == DISPATCH:
        blocked, why = _dispatch_blocked(ctx)
        if blocked:
            return Decision(IDLE, trigger, f"{reason}; dispatch withheld — {why}")

    return Decision(action, trigger, reason)


def read_event_stream(path: str | None = None) -> list[dict[str, Any]]:
    try:
        import wave_kpi

        if path is None:
            return list(wave_kpi.read_events())
        return list(wave_kpi.read_events(path))
    except Exception:
        return []


def route_from_store(
    trigger: str,
    *,
    path: str | None = None,
    checkpoint_every: int = DEFAULT_CHECKPOINT_EVERY,
    max_concurrent_waves: int = MAX_CONCURRENT_WAVES,
    pending_work: bool = False,
    in_quiet_hours: bool = False,
    break_glass_active: bool = False,
    per_day_budget_exceeded: bool = False,
    credit_exhausted: bool = False,
) -> Decision:
    events = read_event_stream(path)
    ctx = TickContext(
        trigger=trigger,
        events=events,
        checkpoint_every=checkpoint_every,
        max_concurrent_waves=max_concurrent_waves,
        pending_work=pending_work,
        in_quiet_hours=in_quiet_hours,
        break_glass_active=break_glass_active,
        per_day_budget_exceeded=per_day_budget_exceeded,
        monthly_credit_exhausted=credit_exhausted,
    )
    return route(ctx)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description='flow_router.py — ORGANISM WS4 HEARTBEAT pure-python event-driven trigger router (P14).')
    ap.add_argument(
        "--trigger",
        required=True,
        choices=sorted(TRIGGERS),
        help="which heartbeat trigger woke the router",
    )
    ap.add_argument("--events", default=None, help="path to the JSONL event store (default: board/.events.jsonl)")
    ap.add_argument("--checkpoint-every", type=int, default=DEFAULT_CHECKPOINT_EVERY,
                    help="N for the after-N-runs validate checkpoint")
    ap.add_argument("--pending-work", action="store_true", help="scheduler signal: actionable board work is waiting")
    ap.add_argument("--quiet-hours", action="store_true", help="SI-4: inside the quiet-hours window")
    ap.add_argument("--break-glass", action="store_true", help="SI-3: an emergency override is live")
    ap.add_argument("--budget-exceeded", action="store_true", help="SI-5: the per-day cost cap is breached")
    ap.add_argument("--credit-exhausted", action="store_true",
                    help="SI-5/FR-004: the monthly subscription credit ceiling is exhausted")
    ap.add_argument("--json", action="store_true", help="emit the decision as JSON")
    args = ap.parse_args(argv)

    decision = route_from_store(
        args.trigger,
        path=args.events,
        checkpoint_every=args.checkpoint_every,
        pending_work=args.pending_work,
        in_quiet_hours=args.quiet_hours,
        break_glass_active=args.break_glass,
        per_day_budget_exceeded=args.budget_exceeded,
        credit_exhausted=args.credit_exhausted,
    )

    if args.json:
        print(json.dumps(decision.as_dict(), indent=2))
    else:
        print(f"{decision.trigger} -> {decision.action}: {decision.reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
