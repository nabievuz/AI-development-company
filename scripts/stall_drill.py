#!/usr/bin/env python3
"""stall_drill.py — ORGANISM WS2 LOOM inner-loop stall/replan self-correction drill.

The P7 inner-loop stall machinery (``scripts/check_ledger.py``) already EXISTS and
is unit-tested, but it is only ever exercised piecemeal by ``tests/test_check_ledger.py``
— never driven end-to-end as a real self-correction *drill*. This module is that
drill: an executable proof that, faced with a genuinely stalling run, the REAL
inner loop

  1. crosses its stall threshold and **replans** — regenerating the task-ledger
     (facts-update + plan-update via ``scripts/task_ledger.py``) and emitting a
     typed ``replanned`` event through ``scripts/dgox/events.py`` (validated here
     with :func:`dgox.events.validate_replanned`); and
  2. when the bounded ``max_replans`` budget is exhausted, **pauses on stall** —
     ``scripts/check_ledger.raise_stall_interrupt_card`` writes a WS1 DAS-1446
     interrupt card to the scratch interrupts dir rather than replanning forever;
     and
  3. **round-trips a Founder resume** — a human answer (``resume:<value>``) written
     onto a scratch ticket is parsed and validated against the card's options and
     turned into a dynamic-tail injection string, via
     ``scripts/interrupt_roundtrip.py`` (``parse_resume_marker`` +
     ``validate_resume_value`` + ``build_resume_injection``).

**Activate, don't duplicate.** The drill imports and calls the real machinery —
``run_inner_loop`` / ``step_inner_loop`` / ``raise_stall_interrupt_card`` and the
``interrupt_roundtrip`` helpers — never a re-implemented copy. It adds NO loop
logic; the stall/replan DECISION stays entirely inside ``check_ledger`` (ADR-0031:
the decision lives in the drill/orchestrator layer, never in ``wave_runner.run_wave``).

**Scratch only.** Every path (runs dir, event store, interrupts dir, ticket) is
passed explicitly and points into a throwaway ``work_dir`` — the drill NEVER writes
to the real ``board/`` (no ``board/interrupts/``, ``board/runs/``, or
``board/.events.jsonl``). ``created_at`` is a fixed injected argument (WS1/WS2
discipline — never a clock read).

Public API
----------
    run_stall_drill(work_dir, *, max_replans=2) -> dict

Exit codes (CLI): 0 = drill passed (replan + pause + resume proven), 1 = a proof
failed, 2 = usage error.

Usage:
    python3 scripts/stall_drill.py --smoke     # run once in a temp workspace
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Make scripts/ importable (same pattern as every other entrypoint).
# ---------------------------------------------------------------------------
_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import check_ledger as cl  # noqa: E402
import interrupt_roundtrip as ir  # noqa: E402
import task_ledger as tl  # noqa: E402
from dgox.events import iter_events, validate_replanned  # noqa: E402

# A fixed, injectable timestamp (no clock read — WS1/WS2 discipline).
_FIXED_TS = "2026-07-04T12:00:00Z"
# The run's anchor ticket (envelope law — every event is ticket-scoped). The
# LOOM inner-loop ticket is a natural anchor; any valid DAS-NNNN id works.
_ANCHOR = "DAS-1470"

# A synthetic *stalling* progress-ledger: ``in_loop`` is True, so the stall rule
# (``in_loop or not progress`` -> stall+1) increments on every single wave — the
# fastest deterministic path to crossing the threshold.
_STALLED_LEDGER: dict[str, Any] = {
    "request_satisfied": False,
    "in_loop": True,
    "progress_being_made": False,
    "next_tickets": ["DAS-2001", "DAS-2002"],
    "instruction": "Loop detected: narrow scope to the failing gate and retry.",
}


class DrillError(AssertionError):
    """A drill proof failed — carries a clear, self-explaining message."""


def _require(condition: bool, message: str) -> None:
    """Raise :class:`DrillError` with *message* unless *condition* holds."""
    if not condition:
        raise DrillError(message)


def _scratch_ticket_body(ticket_id: str, resume_value: str) -> str:
    """Render a minimal scratch ticket .md with a Founder ``resume:<value>`` line.

    The ticket carries valid frontmatter (``status: interrupted``) so it looks
    exactly like a parked interrupt awaiting the Founder; the ``resume:`` marker
    sits in the body, where :func:`interrupt_roundtrip.parse_resume_marker` reads
    it (frontmatter is stripped before the scan).
    """
    return (
        "---\n"
        f"id: {ticket_id}\n"
        "title: Stall drill resume fixture\n"
        "status: interrupted\n"
        "assignee: cto\n"
        "author: ceo\n"
        "dept: engineering\n"
        "priority: p1\n"
        f"created: {_FIXED_TS[:10]}\n"
        f"updated: {_FIXED_TS[:10]}\n"
        "---\n"
        "\n"
        "## Description\n"
        "The inner loop paused on stall; awaiting the Founder's answer.\n"
        "\n"
        f"resume:{resume_value}\n"
        "\n"
        "## Log\n"
        f"### {_FIXED_TS[:10]} — Founder\n"
        "Answered the pause-on-stall gate.\n"
    )


def run_stall_drill(work_dir: Path, *, max_replans: int = 2) -> dict[str, Any]:
    """Drive the REAL inner-loop stall machinery end-to-end in scratch dirs.

    Seeds a synthetic stalling progress-ledger, runs ``check_ledger.run_inner_loop``
    until the ``max_replans`` budget is exhausted (proving >= 1 ``replanned`` event
    then a pause-on-stall interrupt card), and exercises the ``interrupt_roundtrip``
    resume flow against the card the loop wrote. Every path is under *work_dir* — the
    real ``board/`` is never touched.

    Args:
        work_dir:    A throwaway scratch directory (created if absent).
        max_replans: The bounded replan budget for the run. The drill feeds enough
                     stalled waves to consume all of it and then pause; the run
                     therefore emits exactly *max_replans* ``replanned`` events.

    Returns:
        A summary dict:
        ``{run_id, anchor, max_replans, replanned_count, revision, actions,
           paused, card_path, card_id, resume_value, resumed, injection_chars,
           events_validated, board_untouched_paths}``.

    Raises:
        DrillError: if any correctness invariant (replan / card / resume) fails.
    """
    _require(max_replans >= 1, f"max_replans must be >= 1 to prove a replan; got {max_replans}")

    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    # All state lives in scratch — NEVER the real board/ (hard constraint).
    runs_dir = work_dir / "runs"
    store_path = work_dir / "events.jsonl"
    interrupts_dir = work_dir / "interrupts"
    tickets_dir = work_dir / "tickets"
    tickets_dir.mkdir(parents=True, exist_ok=True)

    run_id = tl.generate_ulid()

    # --- 0) Seed the task-ledger the replan will regenerate (must pre-exist). ---
    tl.build_task_ledger(
        run_id=run_id,
        facts=tl.Facts(
            given=["drive the inner-loop stall/replan machinery"],
            known=["wave 0 baseline plan seeded"],
        ),
        plan=[_ANCHOR],
        created_at=_FIXED_TS,
        goal="organism-ws2-loom-stall-drill",
        runs_dir=runs_dir,
    )

    # --- 1) Seed a synthetic stalling progress-ledger + prove it round-trips. ---
    cl.write_progress_ledger(run_id=run_id, runs_dir=runs_dir, **_STALLED_LEDGER)
    seed = cl.read_progress_ledger(run_id, runs_dir)
    _require(
        cl.validate_ledger(seed) == [] and seed == _STALLED_LEDGER,
        f"seed progress-ledger did not round-trip cleanly: {seed!r}",
    )

    # Enough stalled waves to: cross the threshold, replan max_replans times
    # (each replan resets stall to 0), then cross once more with the budget
    # exhausted -> pause. Each crossing costs (STALL_THRESHOLD + 1) increments.
    n_waves = (max_replans + 1) * (cl.STALL_THRESHOLD + 1) + 4
    ledgers = [dict(seed) for _ in range(n_waves)]

    # --- 2) Drive the REAL inner loop. Decision lives in check_ledger (ADR-0031). ---
    # Start the stall counter at the threshold so the first stalled wave crosses.
    state = cl.LoopState(stall=cl.STALL_THRESHOLD, max_replans=max_replans)
    decisions = cl.run_inner_loop(
        ledgers,
        state=state,
        run_id=run_id,
        anchor_ticket=_ANCHOR,
        created_at=_FIXED_TS,
        runs_dir=runs_dir,
        store_path=store_path,
        interrupts_dir=interrupts_dir,
    )
    actions = [d.action for d in decisions]

    # --- 3a) Prove >= 1 replanned event, each schema-valid via the typed validator. ---
    replan_decisions = [d for d in decisions if d.action == "replanned"]
    _require(
        len(replan_decisions) >= 1,
        f"expected >= 1 replanned decision; got actions={actions}",
    )
    replanned_events = list(iter_events(store_path, event_type="replanned"))
    _require(
        len(replanned_events) == len(replan_decisions),
        f"replanned event count {len(replanned_events)} != replanned decisions "
        f"{len(replan_decisions)} (event emission/DECISION mismatch)",
    )
    for ev in replanned_events:
        errs = validate_replanned(ev)
        _require(errs == [], f"replanned event failed validate_replanned: {errs}; event={ev!r}")
        _require(
            ev["ticket_id"] == _ANCHOR and ev["run_id"] == run_id,
            f"replanned event not scoped to this run/anchor: {ev!r}",
        )

    # The task-ledger was actually regenerated (revision bumped by each replan;
    # plan swapped to the stalling ledger's next_tickets).
    after_ledger = tl.read_task_ledger(run_id, runs_dir)
    _require(
        after_ledger["revision"] == 1 + len(replan_decisions),
        f"task-ledger revision {after_ledger['revision']} != "
        f"{1 + len(replan_decisions)} (build=1 + one bump per replan)",
    )
    _require(
        after_ledger["plan"] == _STALLED_LEDGER["next_tickets"],
        f"replan did not adopt next_tickets as the new plan: {after_ledger['plan']!r}",
    )

    # --- 3b) Prove a pause-on-stall interrupt card once the budget is exhausted. ---
    _require(actions[-1] == "paused", f"run did not end in pause-on-stall; actions={actions}")
    _require(state.max_replans == 0, f"replan budget not exhausted at pause; got {state.max_replans}")
    paused = decisions[-1]
    _require(paused.interrupt_card_path is not None, "paused decision carried no interrupt card path")
    card_path = paused.interrupt_card_path
    assert card_path is not None  # for type-checkers; guarded above
    _require(card_path.is_file(), f"interrupt card file not written to scratch: {card_path}")
    _require(
        interrupts_dir in card_path.parents,
        f"interrupt card written outside the scratch interrupts dir: {card_path}",
    )

    # --- 4) Resume round-trip via the REAL interrupt_roundtrip helpers. ---
    # Locate the card the loop wrote (real lookup), and confirm it is that card.
    found = ir.find_interrupt_card(_ANCHOR, interrupts_dir)
    _require(found is not None, f"find_interrupt_card found no card for {_ANCHOR} in {interrupts_dir}")
    assert found is not None  # for type-checkers; guarded above
    found_path, card = found
    _require(
        found_path == card_path,
        f"find_interrupt_card returned {found_path}, expected the paused card {card_path}",
    )
    _require(bool(card.get("options")), f"interrupt card has no answer options: {card!r}")

    # Simulate the human answering: write resume:<value> onto a scratch ticket.
    resume_value = card["options"][0]
    ticket_path = tickets_dir / f"{_ANCHOR}-resume.md"
    ticket_path.write_text(_scratch_ticket_body(_ANCHOR, resume_value), encoding="utf-8")

    # Parse -> validate -> build injection (the real answer->resume flow).
    parsed_value = ir.parse_resume_marker(ticket_path.read_text(encoding="utf-8"))
    _require(
        parsed_value == resume_value,
        f"parse_resume_marker read {parsed_value!r}, expected {resume_value!r}",
    )
    _require(
        ir.validate_resume_value(parsed_value, card),
        f"resume value {parsed_value!r} not accepted against card options {card.get('options')!r}",
    )
    injection = ir.build_resume_injection(parsed_value, card)
    _require(
        resume_value in injection,
        "resume injection does not surface the Founder's answer value",
    )
    _require(
        "dempoten" in injection.lower() or "guard" in injection.lower(),
        "resume injection is missing the mandatory idempotency guard reminder",
    )

    return {
        "run_id": run_id,
        "anchor": _ANCHOR,
        "max_replans": max_replans,
        "replanned_count": len(replanned_events),
        "revision": after_ledger["revision"],
        "actions": actions,
        "paused": actions[-1] == "paused",
        "card_path": str(card_path),
        "card_id": card_path.stem,
        "resume_value": resume_value,
        "resumed": True,
        "injection_chars": len(injection),
        "events_validated": True,
        # The scratch roots the drill drove — proof it never targeted real board/.
        "board_untouched_paths": {
            "runs_dir": str(runs_dir),
            "store_path": str(store_path),
            "interrupts_dir": str(interrupts_dir),
        },
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """Run the stall drill once in a temp workspace; print a one-line summary."""
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--smoke",
        action="store_true",
        help="run one full drill pass in a throwaway temp workspace (default)",
    )
    ap.add_argument(
        "--max-replans",
        type=int,
        default=2,
        help="bounded replan budget to exhaust before pausing (default: 2)",
    )
    ap.add_argument("--keep", action="store_true", help="keep the temp drill directory (debug)")
    args = ap.parse_args(argv)

    if args.max_replans < 1:
        sys.stderr.write("--max-replans must be >= 1\n")
        return 2

    tmp_root = Path(tempfile.mkdtemp(prefix="daslab-stall-drill-"))
    try:
        summary = run_stall_drill(tmp_root / "run", max_replans=args.max_replans)
    except DrillError as exc:
        sys.stderr.write(f"stall-drill FAILED: {exc}\n")
        return 1
    finally:
        if not args.keep:
            import shutil

            shutil.rmtree(tmp_root, ignore_errors=True)

    print(
        "stall-drill: OK — "
        f"replanned x{summary['replanned_count']} (task-ledger rev {summary['revision']}), "
        f"paused-on-stall card {summary['card_id']}, "
        f"resume '{summary['resume_value']}' round-tripped "
        f"({summary['injection_chars']} chars injected)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
