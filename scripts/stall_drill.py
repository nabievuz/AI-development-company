#!/usr/bin/env python3


from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import check_ledger as cl
import interrupt_roundtrip as ir
import task_ledger as tl
from dgox.events import iter_events, validate_replanned

_FIXED_TS = "2026-07-04T12:00:00Z"


_ANCHOR = "DAS-1470"


_STALLED_LEDGER: dict[str, Any] = {
    "request_satisfied": False,
    "in_loop": True,
    "progress_being_made": False,
    "next_tickets": ["DAS-2001", "DAS-2002"],
    "instruction": "Loop detected: narrow scope to the failing gate and retry.",
}


class DrillError(AssertionError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise DrillError(message)


def _scratch_ticket_body(ticket_id: str, resume_value: str) -> str:
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
    _require(max_replans >= 1, f"max_replans must be >= 1 to prove a replan; got {max_replans}")

    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)


    runs_dir = work_dir / "runs"
    store_path = work_dir / "events.jsonl"
    interrupts_dir = work_dir / "interrupts"
    tickets_dir = work_dir / "tickets"
    tickets_dir.mkdir(parents=True, exist_ok=True)

    run_id = tl.generate_ulid()


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


    cl.write_progress_ledger(run_id=run_id, runs_dir=runs_dir, **_STALLED_LEDGER)
    seed = cl.read_progress_ledger(run_id, runs_dir)
    _require(
        cl.validate_ledger(seed) == [] and seed == _STALLED_LEDGER,
        f"seed progress-ledger did not round-trip cleanly: {seed!r}",
    )


    n_waves = (max_replans + 1) * (cl.STALL_THRESHOLD + 1) + 4
    ledgers = [dict(seed) for _ in range(n_waves)]


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


    _require(actions[-1] == "paused", f"run did not end in pause-on-stall; actions={actions}")
    _require(state.max_replans == 0, f"replan budget not exhausted at pause; got {state.max_replans}")
    paused = decisions[-1]
    _require(paused.interrupt_card_path is not None, "paused decision carried no interrupt card path")
    card_path = paused.interrupt_card_path
    assert card_path is not None
    _require(card_path.is_file(), f"interrupt card file not written to scratch: {card_path}")
    _require(
        interrupts_dir in card_path.parents,
        f"interrupt card written outside the scratch interrupts dir: {card_path}",
    )


    found = ir.find_interrupt_card(_ANCHOR, interrupts_dir)
    _require(found is not None, f"find_interrupt_card found no card for {_ANCHOR} in {interrupts_dir}")
    assert found is not None
    found_path, card = found
    _require(
        found_path == card_path,
        f"find_interrupt_card returned {found_path}, expected the paused card {card_path}",
    )
    _require(bool(card.get("options")), f"interrupt card has no answer options: {card!r}")


    resume_value = card["options"][0]
    ticket_path = tickets_dir / f"{_ANCHOR}-resume.md"
    ticket_path.write_text(_scratch_ticket_body(_ANCHOR, resume_value), encoding="utf-8")


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

        "board_untouched_paths": {
            "runs_dir": str(runs_dir),
            "store_path": str(store_path),
            "interrupts_dir": str(interrupts_dir),
        },
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description='stall_drill.py — ORGANISM WS2 LOOM inner-loop stall/replan self-correction drill.')
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
