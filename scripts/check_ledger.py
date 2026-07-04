#!/usr/bin/env python3
"""check_ledger.py — progress-ledger validator + inner-loop stall rule (DAS-1470).

ORGANISM WS2 "LOOM" gives ``/daslab-cycle`` an **inner loop** (GATE-3, P7) that
can tell whether the org is actually making progress or spinning in place, and
self-correct — regenerate its plan, or, when regeneration is exhausted, hand
control back to the Founder rather than burn the run.

This module is the P7 inner loop as a **library + validator**:

  1. **Progress-ledger schema + validator.** After each wave an (opus) planner
     emits ``board/runs/<run_id>/progress-ledger.json`` with the fixed shape::

         {request_satisfied, in_loop, progress_being_made, next_tickets[], instruction}

     :func:`validate_ledger` rejects a ledger with a missing or wrong-typed
     field and accepts a well-formed one.  The CLI (``python3 scripts/check_ledger.py``)
     validates a ledger file and exits non-zero on any problem.

  2. **Stall rule (counter update).** :func:`update_stall` implements::

         in_loop or not progress_being_made  ->  stall = stall + 1
         else                                 ->  stall = max(0, stall - 1)

  3. **REPLAN trigger.** When ``stall > STALL_THRESHOLD`` (>3), the task-ledger is
     regenerated (facts-update + plan-update via ``scripts/task_ledger.py`` —
     EXTEND, not fork), a ``replanned`` event is appended through the typed
     builder in ``scripts/dgox/events.py`` (no raw event dicts), and a bounded
     ``max_replans`` budget is decremented.  The stall counter resets to 0 after a
     replan so the org gets a fresh threshold's worth of waves to recover.

  4. **Pause-on-stall.** When ``max_replans`` is exhausted (0) and a replan would
     otherwise fire, an **interrupt-card** is raised to the Founder
     (``board/interrupts/<id>.json``, the WS1 DAS-1446 schema — reuse, do not
     invent a second halt mechanism).  The run halts awaiting a human
     ``resume:<value>`` rather than looping forever.

Design invariants (EXTEND the WS1/WS2 run-model, do NOT fork it):
- The run-dir scheme + task-ledger regeneration come from ``scripts/task_ledger.py``
  and ``scripts/pulse_checkpoint.py``; this module never re-derives a second
  run-dir scheme or a parallel ledger writer.
- All emitted events go through ``scripts/dgox/events.py`` typed builders.
- ``created_at`` is always an *argument* (injectable for tests — never generated
  inside a pure helper), matching the WS1/WS2 discipline.

Public API
----------
    LEDGER_FIELDS, STALL_THRESHOLD, DEFAULT_MAX_REPLANS
    validate_ledger(ledger)                 -> list[str]
    write_progress_ledger(...)              -> Path
    read_progress_ledger(run_id, ...)       -> dict
    progress_ledger_path(run_id, ...)       -> Path
    update_stall(stall, *, in_loop, progress_being_made) -> int
    LoopState (dataclass: stall, max_replans)
    LoopDecision (dataclass: action, stall, max_replans, replanned, revision,
                  interrupt_card_path)
    raise_stall_interrupt_card(...)         -> Path
    step_inner_loop(...)                    -> LoopDecision
    run_inner_loop(ledgers, ...)            -> list[LoopDecision]

Exit codes (CLI): 0 = ledger valid, 1 = ledger invalid, 2 = usage / IO error.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Reuse the WS1/WS2 run-model conventions (EXTEND, do not fork).  task_ledger
# and pulse_checkpoint own the run-dir scheme + regeneration; dgox.events owns
# the typed event builders.
# ---------------------------------------------------------------------------

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import pulse_checkpoint as _pc  # noqa: E402
import task_ledger as _tl  # noqa: E402
from dgox.events import EventStore, build_replanned  # noqa: E402

# Shared run-dir default — one source of truth (never re-derived here).
DEFAULT_RUNS_DIR: Path = _pc.DEFAULT_RUNS_DIR
DEFAULT_STORE_PATH: Path = _pc.DEFAULT_STORE_PATH
# board/interrupts/ sits beside board/runs/ — derive from the shared runs-dir
# default so there is one root source of truth (no private-attr reach-in).
DEFAULT_INTERRUPTS_DIR: Path = DEFAULT_RUNS_DIR.parent / "interrupts"

_LEDGER_FILENAME = "progress-ledger.json"

#: The fixed progress-ledger schema: field name -> required Python type.
#: ``next_tickets`` is a list of ticket-id strings; the others are scalars.
LEDGER_FIELDS: dict[str, type] = {
    "request_satisfied": bool,
    "in_loop": bool,
    "progress_being_made": bool,
    "next_tickets": list,
    "instruction": str,
}

#: Stall threshold — a replan fires once the counter STRICTLY exceeds this
#: (``stall > 3``), matching the ticket's stall rule.
STALL_THRESHOLD: int = 3

#: Default bounded replan budget for a run.  Each replan decrements it; on
#: exhaustion the loop raises an interrupt-card (pause-on-stall) instead.
DEFAULT_MAX_REPLANS: int = 2

#: The Founder's answer options on a pause-on-stall interrupt card.
_STALL_CARD_OPTIONS: tuple[str, ...] = (
    "replan-again",
    "accept-current-state",
    "abandon",
)


# ---------------------------------------------------------------------------
# Schema validation — the progress-ledger shape
# ---------------------------------------------------------------------------


def validate_ledger(ledger: Any) -> list[str]:
    """Return a list of schema problems for a progress-ledger; empty == valid.

    Validates the fixed shape
    ``{request_satisfied, in_loop, progress_being_made, next_tickets[], instruction}``:

    - the three flags are booleans (``bool``, not truthy ints);
    - ``next_tickets`` is a list of non-empty strings;
    - ``instruction`` is a string (may be empty — a satisfied run needs no steer).

    Does NOT raise — the caller decides whether the errors are fatal.  Extra
    fields are tolerated (the schema is additive).

    Args:
        ledger: The parsed ledger object (expected: a dict).

    Returns:
        A list of human-readable error strings (empty when the ledger is valid).
    """
    errors: list[str] = []
    if not isinstance(ledger, dict):
        return [f"ledger must be a JSON object; got {type(ledger).__name__}"]

    for name, typ in LEDGER_FIELDS.items():
        if name not in ledger:
            errors.append(f"missing required field: {name!r}")
            continue
        value = ledger[name]
        if typ is bool:
            # bool must be a genuine bool (not a truthy int) — the loop branches on it.
            if not isinstance(value, bool):
                errors.append(f"{name!r} must be a boolean; got {value!r}")
        elif typ is list:
            if not isinstance(value, list) or not all(
                isinstance(t, str) and t for t in value
            ):
                errors.append(f"{name!r} must be a list of non-empty strings; got {value!r}")
        elif typ is str and not isinstance(value, str):
            errors.append(f"{name!r} must be a string; got {value!r}")
    return errors


# ---------------------------------------------------------------------------
# Path resolution + read/write — reuse the task_ledger/pulse run-dir scheme
# ---------------------------------------------------------------------------


def _runs_dir(runs_dir: Path | None) -> Path:
    return runs_dir if runs_dir is not None else DEFAULT_RUNS_DIR


def progress_ledger_path(run_id: str, runs_dir: Path | None = None) -> Path:
    """Return ``board/runs/<run_id>/progress-ledger.json`` (canonical run-dir scheme)."""
    return _runs_dir(runs_dir) / run_id / _LEDGER_FILENAME


def write_progress_ledger(
    *,
    run_id: str,
    request_satisfied: bool,
    in_loop: bool,
    progress_being_made: bool,
    next_tickets: list[str],
    instruction: str,
    runs_dir: Path | None = None,
) -> Path:
    """Write a validated ``progress-ledger.json`` for a run.

    The planner (opus) calls this at each wave boundary.  The ledger is validated
    with :func:`validate_ledger` before it touches disk — an ill-formed ledger
    raises ``ValueError`` and nothing is written.

    Returns:
        The path written.

    Raises:
        ValueError: if the ledger fails schema validation.
    """
    ledger = {
        "request_satisfied": request_satisfied,
        "in_loop": in_loop,
        "progress_being_made": progress_being_made,
        "next_tickets": list(next_tickets),
        "instruction": instruction,
    }
    errors = validate_ledger(ledger)
    if errors:
        raise ValueError(f"cannot write invalid progress-ledger (errors: {errors})")
    path = progress_ledger_path(run_id, runs_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ledger, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def read_progress_ledger(run_id: str, runs_dir: Path | None = None) -> dict[str, Any]:
    """Read and validate ``board/runs/<run_id>/progress-ledger.json``.

    Returns:
        The parsed ledger dict.

    Raises:
        FileNotFoundError: if no progress-ledger exists for ``run_id``.
        ValueError:        if the ledger fails schema validation.
    """
    path = progress_ledger_path(run_id, runs_dir)
    if not path.exists():
        raise FileNotFoundError(f"no progress-ledger for run_id {run_id!r} at {path}")
    ledger = json.loads(path.read_text(encoding="utf-8"))
    errors = validate_ledger(ledger)
    if errors:
        raise ValueError(f"invalid progress-ledger at {path} (errors: {errors})")
    return ledger


# ---------------------------------------------------------------------------
# Stall rule — the inner-loop counter update
# ---------------------------------------------------------------------------


def update_stall(stall: int, *, in_loop: bool, progress_being_made: bool) -> int:
    """Apply the stall rule to *stall* for one wave.

    ``in_loop or not progress_being_made  ->  stall + 1``;
    otherwise ``max(0, stall - 1)``.  The counter never goes negative.

    Args:
        stall:               The current stall counter (>= 0).
        in_loop:             Ledger flag: the org is cycling without new ground.
        progress_being_made: Ledger flag: measurable forward motion this wave.

    Returns:
        The updated stall counter.
    """
    if in_loop or not progress_being_made:
        return stall + 1
    return max(0, stall - 1)


# ---------------------------------------------------------------------------
# Inner-loop state + per-wave decision
# ---------------------------------------------------------------------------


@dataclass
class LoopState:
    """Mutable inner-loop state carried across waves of a run.

    - ``stall``       — the stall counter (reset to 0 after each replan).
    - ``max_replans`` — the bounded replan budget remaining (decremented on each
      replan; pause-on-stall fires once it reaches 0).
    """

    stall: int = 0
    max_replans: int = DEFAULT_MAX_REPLANS


@dataclass
class LoopDecision:
    """The outcome of evaluating one wave's progress-ledger.

    - ``action`` ∈ ``{"satisfied", "continue", "replanned", "paused"}``.
    - ``stall`` / ``max_replans`` — the post-step counters.
    - ``replanned`` — True iff the task-ledger was regenerated this step.
    - ``revision`` — the new task-ledger revision when replanned, else ``None``.
    - ``interrupt_card_path`` — the card path when paused-on-stall, else ``None``.
    """

    action: str
    stall: int
    max_replans: int
    replanned: bool = False
    revision: int | None = None
    interrupt_card_path: Path | None = None
    ledger: dict[str, Any] = field(default_factory=dict, repr=False)


# ---------------------------------------------------------------------------
# Task-ledger regeneration on replan — EXTEND scripts/task_ledger.py
# ---------------------------------------------------------------------------


def _regenerate_task_ledger(
    *,
    run_id: str,
    ledger: dict[str, Any],
    wave: int,
    created_at: str,
    runs_dir: Path | None,
) -> int:
    """Regenerate the task-ledger on replan (facts-update + plan-update).

    Reuses ``task_ledger.update_task_ledger`` (the same two-section regeneration
    the ledger already supports — EXTEND, do not fork): the new plan is the
    progress-ledger's ``next_tickets`` (falling back to the existing plan when
    empty), and a ``known`` fact records the stall-triggered replan.  Returns the
    new task-ledger ``revision``.

    Raises:
        FileNotFoundError: if no task-ledger exists to regenerate (the run must
                           have built one at wave-open — DAS-1469).
    """
    existing = _tl.read_task_ledger(run_id, runs_dir)
    facts: _tl.Facts = existing["facts"]
    note = (
        f"Wave {wave}: replanned (stall > {STALL_THRESHOLD}); "
        f"steer: {ledger.get('instruction', '') or '(none)'}"
    )
    new_facts = _tl.Facts(
        given=list(facts.given),
        known=[*facts.known, note],
        to_look_up=list(facts.to_look_up),
        educated_guesses=list(facts.educated_guesses),
    )
    new_plan = list(ledger.get("next_tickets") or existing["plan"])
    _tl.update_task_ledger(
        run_id=run_id,
        created_at=created_at,
        facts=new_facts,
        plan=new_plan,
        wave=wave,
        runs_dir=runs_dir,
    )
    return existing["revision"] + 1


# ---------------------------------------------------------------------------
# Pause-on-stall — raise a WS1 interrupt card (DAS-1446 schema; reuse, no fork)
# ---------------------------------------------------------------------------


def _next_card_id(anchor_ticket: str, interrupts_dir: Path) -> str:
    """Return a unique ``<anchor>-stall-<n>`` card id for *interrupts_dir*."""
    n = 1
    if interrupts_dir.is_dir():
        prefix = f"{anchor_ticket}-stall-"
        existing = 0
        for p in interrupts_dir.glob(f"{prefix}*.json"):
            suffix = p.stem[len(prefix):]
            if suffix.isdigit():
                existing = max(existing, int(suffix))
        n = existing + 1
    return f"{anchor_ticket}-stall-{n}"


def raise_stall_interrupt_card(
    *,
    run_id: str,
    anchor_ticket: str,
    stall: int,
    wave: int,
    instruction: str,
    interrupts_dir: Path | None = None,
    created_by: str = "cto",
) -> Path:
    """Write a pause-on-stall interrupt card to ``board/interrupts/<id>.json``.

    The card conforms to the WS1 DAS-1446 schema
    (``board/interrupts/schema.json``): ``question``, ``options``, ``ticket``,
    ``payload``, ``created_by``.  It is raised when the ``max_replans`` budget is
    exhausted and a replan would otherwise fire — the run halts awaiting a Founder
    ``resume:<value>`` (one of the card's ``options``) rather than replanning
    forever.  This reuses the existing halt mechanism; it does NOT invent a second.

    Args:
        run_id:         ULID run join key (carried in the payload for resume).
        anchor_ticket:  DAS-NNNN id the card is filed under (the run's anchor).
        stall:          The stall counter at the pause.
        wave:           1-based wave index at which the pause fired.
        instruction:    The last planner steer (carried in the payload).
        interrupts_dir: Path to ``board/interrupts/`` (default: canonical).
        created_by:     Role key raising the card (a key from board/ROUTING.md).

    Returns:
        The path of the interrupt card written.
    """
    idir = interrupts_dir if interrupts_dir is not None else DEFAULT_INTERRUPTS_DIR
    idir.mkdir(parents=True, exist_ok=True)
    card_id = _next_card_id(anchor_ticket, idir)
    card = {
        "question": (
            f"The inner loop stalled (stall={stall} > {STALL_THRESHOLD}) and the "
            f"replan budget is exhausted at wave {wave}. How should the run proceed?"
        ),
        "options": list(_STALL_CARD_OPTIONS),
        "ticket": anchor_ticket,
        "payload": {
            "run_id": run_id,
            "wave": wave,
            "stall": stall,
            "instruction": instruction,
            "reason": "pause-on-stall: max_replans exhausted",
        },
        "created_by": created_by,
    }
    path = idir / f"{card_id}.json"
    path.write_text(json.dumps(card, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Per-wave inner-loop step — the P7 decision
# ---------------------------------------------------------------------------


def step_inner_loop(
    *,
    ledger: dict[str, Any],
    state: LoopState,
    run_id: str,
    anchor_ticket: str,
    wave: int,
    created_at: str,
    runs_dir: Path | None = None,
    store_path: Path | None = None,
    interrupts_dir: Path | None = None,
    emit_event: bool = True,
    created_by: str = "cto",
) -> LoopDecision:
    """Evaluate one wave's progress-ledger and advance the inner loop.

    Mutates *state* in place (``stall`` / ``max_replans``) and returns the
    :class:`LoopDecision` describing what happened:

    - ``request_satisfied`` → ``action="satisfied"`` (loop terminates cleanly;
      the stall counter is left unchanged).
    - stall rule keeps ``stall <= STALL_THRESHOLD`` → ``action="continue"``.
    - ``stall > STALL_THRESHOLD`` and budget remains → regenerate the task-ledger,
      emit a ``replanned`` event, decrement ``max_replans``, reset ``stall`` to 0,
      ``action="replanned"``.
    - ``stall > STALL_THRESHOLD`` and budget exhausted → raise an interrupt card,
      ``action="paused"`` (stall is left at its crossed value).

    Args:
        ledger:         The wave's progress-ledger dict (validated here).
        state:          The mutable :class:`LoopState` (advanced in place).
        run_id:         ULID run join key.
        anchor_ticket:  DAS-NNNN anchor ticket for events / interrupt card.
        wave:           1-based wave index.
        created_at:     ISO-8601 UTC timestamp (caller-supplied — injectable).
        runs_dir:       Path to ``board/runs/`` (default: canonical).
        store_path:     Path to the event store (default: canonical).
        interrupts_dir: Path to ``board/interrupts/`` (default: canonical).
        emit_event:     If True (default), append the ``replanned`` event.
        created_by:     Role key for a raised interrupt card.

    Returns:
        The :class:`LoopDecision` for this wave.

    Raises:
        ValueError: if the ledger fails schema validation.
    """
    errors = validate_ledger(ledger)
    if errors:
        raise ValueError(f"cannot step inner loop on invalid ledger (errors: {errors})")

    if ledger["request_satisfied"]:
        return LoopDecision(
            action="satisfied",
            stall=state.stall,
            max_replans=state.max_replans,
            ledger=ledger,
        )

    new_stall = update_stall(
        state.stall,
        in_loop=ledger["in_loop"],
        progress_being_made=ledger["progress_being_made"],
    )

    if new_stall <= STALL_THRESHOLD:
        state.stall = new_stall
        return LoopDecision(
            action="continue",
            stall=state.stall,
            max_replans=state.max_replans,
            ledger=ledger,
        )

    # stall > threshold — a replan is due.
    if state.max_replans > 0:
        revision = _regenerate_task_ledger(
            run_id=run_id,
            ledger=ledger,
            wave=wave,
            created_at=created_at,
            runs_dir=runs_dir,
        )
        state.max_replans -= 1
        state.stall = 0  # fresh threshold's worth of waves to recover
        if emit_event:
            sp = store_path if store_path is not None else DEFAULT_STORE_PATH
            EventStore(sp).append(
                build_replanned(
                    ticket_id=anchor_ticket,
                    run_id=run_id,
                    wave=wave,
                    revision=revision,
                    stall=new_stall,
                    max_replans_remaining=state.max_replans,
                    reason=f"stall {new_stall} > {STALL_THRESHOLD}",
                    created_at=created_at,
                )
            )
        return LoopDecision(
            action="replanned",
            stall=state.stall,
            max_replans=state.max_replans,
            replanned=True,
            revision=revision,
            ledger=ledger,
        )

    # Budget exhausted — pause-on-stall instead of replanning forever.
    card_path = raise_stall_interrupt_card(
        run_id=run_id,
        anchor_ticket=anchor_ticket,
        stall=new_stall,
        wave=wave,
        instruction=ledger.get("instruction", ""),
        interrupts_dir=interrupts_dir,
        created_by=created_by,
    )
    state.stall = new_stall
    return LoopDecision(
        action="paused",
        stall=state.stall,
        max_replans=state.max_replans,
        interrupt_card_path=card_path,
        ledger=ledger,
    )


def run_inner_loop(
    ledgers: list[dict[str, Any]],
    *,
    state: LoopState,
    run_id: str,
    anchor_ticket: str,
    created_at: str,
    first_wave: int = 1,
    runs_dir: Path | None = None,
    store_path: Path | None = None,
    interrupts_dir: Path | None = None,
    emit_event: bool = True,
    created_by: str = "cto",
) -> list[LoopDecision]:
    """Drive the inner loop over a sequence of per-wave progress-ledgers.

    Steps each ledger in order (wave = ``first_wave`` + index).  Iteration stops
    early on a terminal decision: ``action="satisfied"`` (clean termination) or
    ``action="paused"`` (halted awaiting a Founder ``resume:<value>``).  A
    ``replanned`` step continues the loop.

    Returns:
        The list of :class:`LoopDecision`, one per ledger processed (may be
        shorter than *ledgers* when the loop terminates or pauses early).
    """
    decisions: list[LoopDecision] = []
    for i, ledger in enumerate(ledgers):
        decision = step_inner_loop(
            ledger=ledger,
            state=state,
            run_id=run_id,
            anchor_ticket=anchor_ticket,
            wave=first_wave + i,
            created_at=created_at,
            runs_dir=runs_dir,
            store_path=store_path,
            interrupts_dir=interrupts_dir,
            emit_event=emit_event,
            created_by=created_by,
        )
        decisions.append(decision)
        if decision.action in ("satisfied", "paused"):
            break
    return decisions


# ---------------------------------------------------------------------------
# CLI — validate a progress-ledger.json file
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """Validate a ``progress-ledger.json`` against the fixed schema.

    Accepts either a direct ``--path`` to a ledger file, or a ``--run-id`` (+
    optional ``--runs-dir``) resolving to the canonical run-dir location.
    """
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--path", type=Path, help="path to a progress-ledger.json file")
    src.add_argument("--run-id", type=str, help="run id (resolves to board/runs/<run_id>/)")
    ap.add_argument("--runs-dir", type=Path, default=None, help="override board/runs/ location")
    args = ap.parse_args(argv)

    path = args.path if args.path is not None else progress_ledger_path(args.run_id, args.runs_dir)

    if not path.is_file():
        sys.stderr.write(f"ERROR: progress-ledger not found: {path}\n")
        return 2
    try:
        ledger = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"ERROR: cannot read/parse {path}: {exc}\n")
        return 2

    problems = validate_ledger(ledger)
    if problems:
        sys.stderr.write(f"FAIL: invalid progress-ledger ({path}):\n")
        for p in problems:
            sys.stderr.write(f"  - {p}\n")
        return 1
    print(f"OK: progress-ledger valid ({path}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
