#!/usr/bin/env python3
"""flow_router.py — ORGANISM WS4 HEARTBEAT pure-python event-driven trigger router (P14).

The "heartbeat" that turns the org's operator tempo into **deterministic arrows
between autonomous boxes**. Given a *trigger* (why the heartbeat woke) and the
observed event stream (`board/.events.jsonl`), it decides exactly one tempo action:

    dispatch  — the org should run the next wave (hand off to /daslab-cycle)
    validate  — run the validator suite (a read-only checkpoint)
    idle      — do nothing this tick

It is a PURE-PYTHON decision function: **NO LLM call anywhere**, no network, no
clock read, no timer, no thread, no background loop. Same trigger + same event
stream (+ same declared context) → same decision, every time (deterministic
arrows). Each decision hands off to an already-autonomous executor (autonomous
boxes); the router itself never dispatches a wave, never edits a ticket, and
never writes an event — it only *returns* a `Decision`.

Declarative trigger table (the 5 triggers of the WS4 spec)
----------------------------------------------------------
    on ticket_created      -> consider dispatch of the next wave
    on wave_completed      -> run validators, then decide the next tick
    on interrupt_answered  -> resume (dispatch) — NEVER auto-answers (SI-7)
    on after_n_runs        -> periodic validate / idle checkpoint
    on cron_tick           -> time-based tick (dispatch / validate / idle)

Reader scope (ADR-0025 — load-bearing but SCOPED)
-------------------------------------------------
Events are read through the existing load-bearing reader `wave_kpi.read_events`
(never a re-implemented parser; never a `dgox.*` import). Per ADR-0025 this
operator-tempo reader is load-bearing but scoped: it decides **WHETHER (and what
kind of) tick** should happen next — the in-flight/run-count *tempo* facts — and
NEVER a normal-dispatch routing decision (which ticket, which role, which model).
The router writes no `board/tickets/*.md` routing field, so under the ADR-0025
principled reader-vs-router rule (`tests/test_dgox_phase1_shadow.py` P1) it
"reads but does not route" ⇒ it is not a shadow-rule violation.

Scheduler-safety invariants honored (ADR-0027 SI-1..SI-7)
---------------------------------------------------------
    SI-1  One-shot: this module holds no process, loop, or self-rescheduling
          timer. `route()` evaluates once and returns. Cadence, if any, lives in
          an external Founder-owned OS scheduler, never here.
    SI-3  Break-glass kill-switch (`break_glass_active`) forces every dispatch to
          idle while an override is live.
    SI-4  Quiet hours (`in_quiet_hours`) force a dispatch tick to idle.
    SI-5  Per-day budget breach (`per_day_budget_exceeded`) forces dispatch to
          idle.
    SI-6  Max 1 wave: if a wave is already in flight (a `run_start` with no
          matching `run_end`), a dispatch tick evaluates to idle — never a
          stacked/overlapping wave.
    SI-7  Never auto-approve: the decision set is exactly {dispatch, validate,
          idle}. There is no "answer"/"approve" action — structurally the router
          cannot sign a gate or answer an interrupt-card. `interrupt_answered`
          dispatches only because a human already wrote the `resume:` answer; the
          router never synthesizes, defaults, or infers that answer.

Failure isolation
-----------------
A malformed event, an unknown trigger, a reader error, or any exception in a
handler degrades to `idle` — the router never crashes the tempo loop and never
escalates a gate.

Usage (library):
    from flow_router import TickContext, route, route_from_store
    decision = route(TickContext(trigger="ticket_created", events=events))
    decision = route_from_store("wave_completed")   # reads board/.events.jsonl

Usage (CLI, an evaluator/reporter — never a mutator, exit 0):
    python3 scripts/flow_router.py --trigger ticket_created
    python3 scripts/flow_router.py --trigger cron_tick --pending-work
"""
from __future__ import annotations

import argparse
import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

# --------------------------------------------------------------------------- #
# Decisions — the closed output alphabet (SI-7: no "answer"/"approve" action).
# --------------------------------------------------------------------------- #

DISPATCH = "dispatch"
VALIDATE = "validate"
IDLE = "idle"

#: The exact, closed set of decisions the router may ever return. It deliberately
#: contains NO gate/interrupt-answering action — the never-auto-approve law is
#: enforced structurally, not by a runtime check (ADR-0027 SI-7).
DECISIONS: frozenset[str] = frozenset({DISPATCH, VALIDATE, IDLE})

# --------------------------------------------------------------------------- #
# Triggers — the declarative trigger table's keys (WS4 spec, 5 triggers).
# --------------------------------------------------------------------------- #

TICKET_CREATED = "ticket_created"
WAVE_COMPLETED = "wave_completed"
INTERRUPT_ANSWERED = "interrupt_answered"
AFTER_N_RUNS = "after_n_runs"
CRON_TICK = "cron_tick"

#: The 5 triggers the router understands. An unknown trigger is failure-isolated
#: to ``idle`` (never a crash).
TRIGGERS: frozenset[str] = frozenset(
    {TICKET_CREATED, WAVE_COMPLETED, INTERRUPT_ANSWERED, AFTER_N_RUNS, CRON_TICK}
)

#: Default cadence for the periodic validate checkpoint (after every N runs).
DEFAULT_CHECKPOINT_EVERY = 10

#: SI-6 — the autonomous substrate runs at most one wave at a time.
MAX_CONCURRENT_WAVES = 1


# --------------------------------------------------------------------------- #
# Value objects
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Decision:
    """One tempo decision — the deterministic arrow this tick produces.

    Attributes:
        action:  one of :data:`DECISIONS` (``dispatch`` / ``validate`` / ``idle``).
        trigger: the trigger that produced it (echoed for audit/logging).
        reason:  human-readable rationale (deterministic; no timestamps/ids).
    """

    action: str
    trigger: str
    reason: str

    def as_dict(self) -> dict[str, str]:
        return {"action": self.action, "trigger": self.trigger, "reason": self.reason}


@dataclass(frozen=True)
class TickContext:
    """All inputs a single ``--tick`` decision depends on (no hidden state).

    Every fact the router needs is an explicit field so the decision is a pure
    function of its inputs (determinism). The tempo facts (in-flight, run count)
    are derived from ``events``; the safety facts (SI-3/4/5) are supplied by the
    caller (the scheduler, which owns break-glass / quiet-hours / budget reads).

    Attributes:
        trigger:                which of :data:`TRIGGERS` woke the heartbeat.
        events:                 the event stream (as read by
                                ``wave_kpi.read_events``); tempo facts derive
                                from it. Tolerant of malformed entries.
        checkpoint_every:       N for the after-N-runs validate checkpoint.
        max_concurrent_waves:   SI-6 ceiling (1 for the autonomous substrate).
        pending_work:           scheduler-supplied — is there actionable board
                                work waiting? (drives the cron_tick dispatch arm).
        in_quiet_hours:         SI-4 — inside the configured quiet window.
        break_glass_active:     SI-3 — an emergency override is live.
        per_day_budget_exceeded: SI-5 — the per-day cost cap is already breached.
    """

    trigger: str
    events: Sequence[dict[str, Any]] = field(default_factory=tuple)
    checkpoint_every: int = DEFAULT_CHECKPOINT_EVERY
    max_concurrent_waves: int = MAX_CONCURRENT_WAVES
    pending_work: bool = False
    in_quiet_hours: bool = False
    break_glass_active: bool = False
    per_day_budget_exceeded: bool = False


# --------------------------------------------------------------------------- #
# Tempo facts derived from the event stream (the "whether to tick" reader —
# ADR-0025 scope: never a per-ticket routing decision).
# --------------------------------------------------------------------------- #


def _runs_in_flight(events: Sequence[dict[str, Any]]) -> set[str]:
    """run_ids with a ``run_start`` but no matching ``run_end`` (SI-6 basis).

    Tolerant of malformed events: non-dict entries and rows without a usable
    ``run_id`` are skipped, never raised on.
    """
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
    """Number of completed runs (``run_end`` events) — the after-N-runs basis."""
    return sum(
        1
        for ev in events
        if isinstance(ev, dict) and ev.get("event_type") == "run_end"
    )


def _wave_in_flight(ctx: TickContext) -> bool:
    """True when a heartbeat-dispatched wave is still running (SI-6)."""
    return len(_runs_in_flight(ctx.events)) >= ctx.max_concurrent_waves


def _dispatch_blocked(ctx: TickContext) -> tuple[bool, str]:
    """Whether a would-be dispatch must degrade to idle, and why.

    Enforces the ADR-0027 dispatch gates uniformly for every trigger that wants
    to dispatch — order fixed for a deterministic reason string:
    SI-3 break-glass, SI-4 quiet hours, SI-5 per-day budget, SI-6 wave-in-flight.
    """
    if ctx.break_glass_active:
        return True, "break-glass override active (SI-3)"
    if ctx.in_quiet_hours:
        return True, "inside quiet-hours window (SI-4)"
    if ctx.per_day_budget_exceeded:
        return True, "per-day budget cap already breached (SI-5)"
    if _wave_in_flight(ctx):
        return True, "a wave is already in flight, max 1 (SI-6)"
    return False, ""


# --------------------------------------------------------------------------- #
# Trigger handlers — the declarative table. Each returns (tentative_action,
# reason). A tentative ``dispatch`` is passed through the SI-3..SI-6 gate in
# route(); validate/idle are always safe (read-only / no-op).
# --------------------------------------------------------------------------- #


def _on_ticket_created(ctx: TickContext) -> tuple[str, str]:
    """A new ticket exists → consider dispatching the next wave."""
    return DISPATCH, "ticket_created: new work exists — dispatch the next wave"


def _on_wave_completed(ctx: TickContext) -> tuple[str, str]:
    """A wave just finished → run validators before deciding the next tick."""
    return VALIDATE, "wave_completed: run validators, then decide the next tick"


def _on_interrupt_answered(ctx: TickContext) -> tuple[str, str]:
    """A human answered an interrupt-card (``resume:`` written) → dispatch to resume.

    SI-7: the router NEVER auto-answers. It dispatches only because the trigger
    itself signals a human already supplied the answer; it never synthesizes,
    defaults, or infers a ``resume:`` value.
    """
    return (
        DISPATCH,
        "interrupt_answered: human wrote resume — dispatch to resume "
        "(router never auto-answers, SI-7)",
    )


def _on_after_n_runs(ctx: TickContext) -> tuple[str, str]:
    """Every N completed runs → a periodic validate checkpoint; otherwise idle."""
    n = _completed_run_count(ctx.events)
    every = ctx.checkpoint_every
    if every > 0 and n > 0 and n % every == 0:
        return VALIDATE, f"after_n_runs: {n} runs completed (multiple of {every}) — validate checkpoint"
    return IDLE, f"after_n_runs: {n} runs completed — no checkpoint due"


def _on_cron_tick(ctx: TickContext) -> tuple[str, str]:
    """Time-based tick → dispatch pending work, else validate-if-due, else idle.

    A blind timer is conservative (ADR-0027 bounded blast radius): it dispatches
    ONLY when the scheduler signals ``pending_work`` (and the SI-3..SI-6 gate in
    route() still applies). With nothing pending it falls to the same periodic
    validate checkpoint as after_n_runs, else idles.
    """
    if ctx.pending_work:
        return DISPATCH, "cron_tick: pending board work — dispatch the next wave"
    n = _completed_run_count(ctx.events)
    every = ctx.checkpoint_every
    if every > 0 and n > 0 and n % every == 0:
        return VALIDATE, f"cron_tick: {n} runs completed (multiple of {every}) — validate checkpoint"
    return IDLE, "cron_tick: nothing pending, no checkpoint due — idle"


#: The declarative trigger table: trigger -> handler. This IS the router's core.
_HANDLERS: dict[str, Callable[[TickContext], tuple[str, str]]] = {
    TICKET_CREATED: _on_ticket_created,
    WAVE_COMPLETED: _on_wave_completed,
    INTERRUPT_ANSWERED: _on_interrupt_answered,
    AFTER_N_RUNS: _on_after_n_runs,
    CRON_TICK: _on_cron_tick,
}


# --------------------------------------------------------------------------- #
# The router
# --------------------------------------------------------------------------- #


def route(ctx: TickContext) -> Decision:
    """Evaluate one tick and return exactly one :class:`Decision`.

    Deterministic (same context → same decision) and failure-isolated (any
    exception, unknown trigger, or non-decision handler output degrades to
    ``idle``). A tentative ``dispatch`` is gated by SI-3..SI-6; if blocked it
    degrades to ``idle`` with a precise reason (never a crash, never a stacked
    wave, never a gate signed).
    """
    trigger = ctx.trigger
    handler = _HANDLERS.get(trigger)
    if handler is None:
        return Decision(IDLE, str(trigger), f"unknown trigger {trigger!r} — degraded to idle")

    try:
        action, reason = handler(ctx)
    except Exception as exc:  # noqa: BLE001 — failure isolation is the contract
        return Decision(IDLE, trigger, f"handler error degraded to idle: {exc!r}")

    if action not in DECISIONS:
        return Decision(IDLE, trigger, f"handler returned non-decision {action!r} — degraded to idle")

    if action == DISPATCH:
        blocked, why = _dispatch_blocked(ctx)
        if blocked:
            return Decision(IDLE, trigger, f"{reason}; dispatch withheld — {why}")

    return Decision(action, trigger, reason)


def read_event_stream(path: str | None = None) -> list[dict[str, Any]]:
    """Read the event stream via the load-bearing ``wave_kpi.read_events`` reader.

    Reuses the existing reader (ADR-0025) rather than re-parsing JSONL; never
    imports ``dgox.*``. Fully failure-isolated: a missing store, a reader error,
    or any exception yields ``[]`` (the tempo loop degrades to idle, never
    crashes). ``wave_kpi.read_events`` already returns ``[]`` for a missing file
    and skips malformed lines; this wrapper additionally guards the import and
    any unexpected error.
    """
    try:
        import wave_kpi  # noqa: PLC0415 — lazy: keeps import-time clean, no dgox

        if path is None:
            return list(wave_kpi.read_events())
        return list(wave_kpi.read_events(path))
    except Exception:  # noqa: BLE001 — reader failure must not break the tick
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
) -> Decision:
    """Convenience entry: read the event store, then :func:`route` one tick.

    This is the single place the router touches the event store. It composes
    :func:`read_event_stream` (the ADR-0025 scoped reader) with :func:`route`,
    so the safety facts (SI-3/4/5) stay explicit caller inputs while the tempo
    facts (SI-6 in-flight, after-N-runs) come from the stream.
    """
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
    )
    return route(ctx)


# --------------------------------------------------------------------------- #
# CLI — an evaluator/reporter, never a mutator (exit 0, like loop_controller).
# --------------------------------------------------------------------------- #


def main(argv: list[str] | None = None) -> int:
    """Print the tempo decision for one trigger. Never dispatches, never mutates."""
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
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
    )

    if args.json:
        print(json.dumps(decision.as_dict(), indent=2))
    else:
        print(f"{decision.trigger} -> {decision.action}: {decision.reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
