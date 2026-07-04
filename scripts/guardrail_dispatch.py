#!/usr/bin/env python3
"""guardrail_dispatch.py — INPUT/OUTPUT guardrail dispatch wrapper (DAS-1471).

The closed-loop "tripwire" for ORGANISM WS2 LOOM (GATE-3 / P10). Wraps a single
ticket dispatch:

    INPUT screen (pre-accept)  →  accept  →  run agent  →  OUTPUT screen
        │ trip                                                │ trip
        └─ refuse (do not accept, re-route)                  ▼
                                       write feedback into ticket
                                       (origin: output_guardrail)
                                       + re-dispatch the SAME agent
                                       (max 2 retries)
                                                │ still tripping after 2
                                                ▼
                                       escalate per board/ROUTING.md
                                       (failing role's reviewer;
                                        manager-is-author → one level up)

The wrapper is deterministic and side-effect-scoped to the ticket file: it never
spawns a subagent itself. The caller injects ``run_agent`` (the thing that
produces the agent's output for one attempt) so the loop is fully testable.

Reuses:
* ``guardrails.runner`` — role guardrail loading + context assembly.
* ``board/ROUTING.md`` role table — the reviewer/escalation chain (the same map
  ``/daslab-cycle`` step 2 parses; not re-invented here).

CLI (``--ticket``) runs the INPUT scope screen only and reports ok/feedback —
the OUTPUT retry loop needs a live agent and is driven via the library API.

Exit codes (CLI): 0 = INPUT screen passed, 1 = INPUT screen tripped, 2 = usage.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from _paths import ROOT

# Make the guardrails package importable (it lives under governance/, not scripts/).
_GOVERNANCE_DIR = ROOT / "governance"
if str(_GOVERNANCE_DIR) not in sys.path:
    sys.path.insert(0, str(_GOVERNANCE_DIR))

from guardrails import GuardrailContext  # noqa: E402
from guardrails import runner as _runner  # noqa: E402

DEFAULT_ROUTING = ROOT / "board" / "ROUTING.md"
DEFAULT_BOARD = ROOT / "board" / "tickets"
DEFAULT_MAX_RETRIES = 2

# The origin tag distinguishing guardrail feedback from a human reviewer's notes.
OUTPUT_GUARDRAIL_ORIGIN = "output_guardrail"


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass
class DispatchResult:
    """Outcome of one guarded dispatch."""

    ticket_id: str
    role: str
    accepted: bool                       # did the INPUT screen accept the ticket?
    outcome: str                         # "input_rejected" | "passed" | "escalated"
    attempts: int = 0                    # total agent runs (initial + retries)
    retries_used: int = 0                # re-dispatches after the initial run
    feedback: str = ""                   # last guardrail feedback (empty on pass)
    escalated_to: str | None = None      # reviewer role key when outcome=escalated
    feedback_log: list[str] = field(default_factory=list)  # every OUTPUT feedback written


# ---------------------------------------------------------------------------
# Escalation chain (reuse ROUTING.md role table)
# ---------------------------------------------------------------------------


def escalation_target(
    role: str, author: str, role_table: dict[str, dict[str, str]]
) -> str | None:
    """Return the role key the *role* escalates to per ROUTING.md.

    The failing role's "Reports to (reviewer)" is resolved to a role key. If that
    reviewer IS the ticket author (manager-is-author), climb one level up (the
    same rule board_lint applies to ``in_review`` reassignment). Returns ``None``
    when the chain has no higher role (top of the org).
    """
    display_to_key = {v["display"]: k for k, v in role_table.items()}
    reports_to = role_table.get(role, {}).get("reports_to", "")
    reviewer = display_to_key.get(reports_to)
    if reviewer and reviewer == author:
        up = role_table.get(reviewer, {}).get("reports_to", "")
        reviewer = display_to_key.get(up, reviewer)
    return reviewer


# ---------------------------------------------------------------------------
# Ticket mutation — feedback + escalation (append-only log; scoped frontmatter)
# ---------------------------------------------------------------------------


def _today() -> str:
    return _dt.date.today().isoformat()


def write_output_guardrail_feedback(
    ticket_path: Path,
    feedback: str,
    *,
    role: str,
    attempt: int,
    max_retries: int,
    now: Callable[[], str] = _today,
) -> str:
    """Append an OUTPUT-guardrail feedback log entry (``origin: output_guardrail``).

    Returns the entry text written. ``attempt`` is 0-based (0 = initial run).
    """
    retry_no = attempt + 1
    entry = (
        f"\n### {now()} — Output guardrail ({role})\n"
        f"origin: {OUTPUT_GUARDRAIL_ORIGIN}\n"
        f"Retry {retry_no}/{max_retries}: {feedback}\n"
        f"Re-dispatching {role} with this feedback so it can self-correct.\n"
    )
    with ticket_path.open("a", encoding="utf-8") as fh:
        fh.write(entry)
    return entry


def _set_frontmatter_field(text: str, key: str, value: str) -> str:
    """Return *text* with frontmatter ``key`` set to ``value`` (added if absent)."""
    pattern = re.compile(rf"^({re.escape(key)}:)[^\n]*$", re.MULTILINE)
    if pattern.search(text):
        return pattern.sub(rf"\1 {value}", text, count=1)
    # Insert before the closing '---' of the frontmatter block.
    m = re.match(r"^---\s*\n(.*?\n)---\s*\n", text, re.DOTALL)
    if not m:
        return text
    insert_at = m.start(1) + len(m.group(1))
    return text[:insert_at] + f"{key}: {value}\n" + text[insert_at:]


def escalate_in_ticket(
    ticket_path: Path,
    target: str | None,
    role: str,
    feedback: str,
    *,
    max_retries: int,
    now: Callable[[], str] = _today,
) -> None:
    """Escalate the ticket: reassign to *target*, mark ``in_review``, log why."""
    text = ticket_path.read_text(encoding="utf-8")
    if target:
        text = _set_frontmatter_field(text, "assignee", target)
        text = _set_frontmatter_field(text, "status", "in_review")
        text = _set_frontmatter_field(text, "updated", now())
    dest = target or "(top of org — no higher reviewer)"
    entry = (
        f"\n### {now()} — Guardrail escalation ({role} → {dest})\n"
        f"origin: {OUTPUT_GUARDRAIL_ORIGIN}\n"
        f"Exhausted {max_retries} retries; OUTPUT guardrail still tripping: {feedback}\n"
        f"Escalating per board/ROUTING.md to {dest} for review.\n"
    )
    ticket_path.write_text(text + entry, encoding="utf-8")


# ---------------------------------------------------------------------------
# The dispatch loop
# ---------------------------------------------------------------------------


def guardrail_dispatch(
    ticket_path: Path,
    run_agent: Callable[[GuardrailContext, int], str],
    *,
    routing_path: Path = DEFAULT_ROUTING,
    board_dir: Path = DEFAULT_BOARD,
    guardrails_dir: Path = _runner.DEFAULT_GUARDRAILS_DIR,
    max_retries: int = DEFAULT_MAX_RETRIES,
    gate_open: bool = False,
    now: Callable[[], str] = _today,
) -> DispatchResult:
    """Run one guarded dispatch of *ticket_path*.

    ``run_agent(ctx, attempt)`` returns the agent's produced output for that
    attempt (0-based). The wrapper handles INPUT screening, OUTPUT screening,
    feedback-writing, bounded re-dispatch, and escalation.
    """
    ticket_path = Path(ticket_path)
    ctx = _runner.build_context(
        ticket_path,
        routing_path=routing_path,
        board_dir=board_dir,
        gate_open=gate_open,
    )
    role = ctx.role
    role_table = _runner.load_role_table(routing_path)
    author = ctx.frontmatter.get("author", "").strip()

    # --- INPUT screen (pre-accept) -----------------------------------------
    ok, feedback = _runner.run_input(role, ctx, guardrails_dir)
    if not ok:
        return DispatchResult(
            ticket_id=ctx.ticket_id,
            role=role,
            accepted=False,
            outcome="input_rejected",
            feedback=feedback,
        )

    # --- accept → run agent → OUTPUT screen → retry-with-feedback -----------
    feedback_log: list[str] = []
    last_feedback = ""
    for attempt in range(max_retries + 1):  # initial (0) + up to max_retries
        output = run_agent(ctx, attempt)
        ctx.output = output
        ok, feedback = _runner.run_output(role, ctx, guardrails_dir)
        if ok:
            return DispatchResult(
                ticket_id=ctx.ticket_id,
                role=role,
                accepted=True,
                outcome="passed",
                attempts=attempt + 1,
                retries_used=attempt,
                feedback_log=feedback_log,
            )
        last_feedback = feedback
        write_output_guardrail_feedback(
            ticket_path, feedback, role=role, attempt=attempt,
            max_retries=max_retries, now=now,
        )
        feedback_log.append(feedback)

    # --- exhausted retries → escalate --------------------------------------
    target = escalation_target(role, author, role_table)
    escalate_in_ticket(
        ticket_path, target, role, last_feedback,
        max_retries=max_retries, now=now,
    )
    return DispatchResult(
        ticket_id=ctx.ticket_id,
        role=role,
        accepted=True,
        outcome="escalated",
        attempts=max_retries + 1,
        retries_used=max_retries,
        feedback=last_feedback,
        escalated_to=target,
        feedback_log=feedback_log,
    )


# ---------------------------------------------------------------------------
# Wave-level pre-dispatch INPUT screen (R3 — dispatch-time scope screening)
# ---------------------------------------------------------------------------


@dataclass
class WaveScreenResult:
    """Outcome of the wave-level pre-dispatch INPUT scope screen (R3)."""

    accepted: list[str] = field(default_factory=list)   # ticket ids cleared to dispatch
    rejected: list[dict] = field(default_factory=list)  # {ticket_id, role, dept, feedback, reroute_to}

    @property
    def all_accepted(self) -> bool:
        return not self.rejected

    @property
    def rejected_ids(self) -> list[str]:
        return [r["ticket_id"] for r in self.rejected]


def screen_wave_inputs(
    ticket_paths: list[Path],
    *,
    routing_path: Path = DEFAULT_ROUTING,
    board_dir: Path = DEFAULT_BOARD,
    guardrails_dir: Path = _runner.DEFAULT_GUARDRAILS_DIR,
    gate_open_ids: set[str] | None = None,
) -> WaveScreenResult:
    """Run the INPUT scope screen over a WAVE's candidate tickets BEFORE dispatch.

    This is R3's deterministic dispatch-time gate, placed at the ORCHESTRATOR
    decision point (pre-dispatch) — deliberately NOT inside ``wave_runner``, which
    stays post-decision with *no decision inside it* (ADR-0031: flag-on ==
    flag-off dispatch decisions). The orchestrator calls this to refuse / re-route
    out-of-scope candidates (wrong-department, a missing declared ``consumes``
    input, or an open predecessor gate) before any is dispatched; only
    ``result.accepted`` ids proceed to a wave.

    ``gate_open_ids`` names candidates whose AADL predecessor gate is still open
    (the orchestrator supplies this from the stage-gate state).
    """
    open_ids = set(gate_open_ids or ())
    result = WaveScreenResult()
    for ticket_path in ticket_paths:
        ctx = _runner.build_context(
            Path(ticket_path), routing_path=routing_path, board_dir=board_dir
        )
        ctx.gate_open = ctx.ticket_id in open_ids
        ok, feedback = _runner.run_input(ctx.role, ctx, guardrails_dir)
        if ok:
            result.accepted.append(ctx.ticket_id)
        else:
            result.rejected.append({
                "ticket_id": ctx.ticket_id,
                "role": ctx.role,
                "dept": ctx.ticket_dept,
                "feedback": feedback,
                # a wrong-department ticket re-routes to its declared owning dept.
                "reroute_to": ctx.ticket_dept or None,
            })
    return result


# ---------------------------------------------------------------------------
# CLI — INPUT scope screen only (the OUTPUT loop needs a live agent)
# ---------------------------------------------------------------------------


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--ticket", type=Path, help="Path to a DAS-*.md ticket (single INPUT screen)")
    src.add_argument(
        "--screen-wave", type=Path, metavar="DIR",
        help="Screen every DAS-*.md in DIR — the wave-level pre-dispatch INPUT gate (R3)",
    )
    p.add_argument("--routing", type=Path, default=DEFAULT_ROUTING)
    p.add_argument("--board", type=Path, default=DEFAULT_BOARD)
    p.add_argument(
        "--gate-open",
        action="store_true",
        help="Signal an open AADL predecessor gate (input screen trips on it).",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)

    if args.screen_wave is not None:
        wave_dir = args.screen_wave
        if not wave_dir.is_dir():
            print(f"ERROR: not a directory: {wave_dir}", file=sys.stderr)
            return 2
        tickets = sorted(wave_dir.glob("DAS-*.md"))
        res = screen_wave_inputs(tickets, routing_path=args.routing, board_dir=args.board)
        print(
            f"guardrail_dispatch: wave INPUT screen — {len(res.accepted)} accepted, "
            f"{len(res.rejected)} rejected (of {len(tickets)} candidate ticket(s))."
        )
        for r in res.rejected:
            print(f"  REJECT {r['ticket_id']} ({r['role']}): {r['feedback']}", file=sys.stderr)
        return 1 if res.rejected else 0

    if not args.ticket.is_file():
        print(f"ERROR: ticket not found: {args.ticket}", file=sys.stderr)
        return 2
    ctx = _runner.build_context(
        args.ticket,
        routing_path=args.routing,
        board_dir=args.board,
        gate_open=args.gate_open,
    )
    ok, feedback = _runner.run_input(ctx.role, ctx)
    if ok:
        print(f"guardrail_dispatch: INPUT screen OK — {ctx.ticket_id} ({ctx.role}) accepted.")
        return 0
    print(f"guardrail_dispatch: INPUT screen TRIPPED — {ctx.ticket_id} ({ctx.role})")
    print(f"  FEEDBACK  {feedback}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
