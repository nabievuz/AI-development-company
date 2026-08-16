#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as _dt
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import filelock as _fl
from _paths import ROOT

_GOVERNANCE_DIR = ROOT / "governance"
if str(_GOVERNANCE_DIR) not in sys.path:
    sys.path.insert(0, str(_GOVERNANCE_DIR))

from guardrails import GuardrailContext
from guardrails import runner as _runner

DEFAULT_ROUTING: Path | None = None
LEGACY_ROUTING_MD = ROOT / "board" / "ROUTING.md"
DEFAULT_BOARD = ROOT / "board" / "tickets"
DEFAULT_MAX_RETRIES = 2


OUTPUT_GUARDRAIL_ORIGIN = "output_guardrail"


@dataclass
class DispatchResult:

    ticket_id: str
    role: str
    accepted: bool
    outcome: str
    attempts: int = 0
    retries_used: int = 0
    feedback: str = ""
    escalated_to: str | None = None
    feedback_log: list[str] = field(default_factory=list)


def escalation_target(
    role: str, author: str, role_table: dict[str, dict[str, str]]
) -> str | None:
    display_to_key = {v["display"]: k for k, v in role_table.items()}
    reports_to = role_table.get(role, {}).get("reports_to", "")
    reviewer = display_to_key.get(reports_to)
    if reviewer and reviewer == author:
        up = role_table.get(reviewer, {}).get("reports_to", "")
        reviewer = display_to_key.get(up, reviewer)
    return reviewer


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
    retry_no = attempt + 1
    entry = (
        f"\n### {now()} — Output guardrail ({role})\n"
        f"origin: {OUTPUT_GUARDRAIL_ORIGIN}\n"
        f"Retry {retry_no}/{max_retries}: {feedback}\n"
        f"Re-dispatching {role} with this feedback so it can self-correct.\n"
    )
    _fl.locked_append_text(ticket_path, entry)
    return entry


HALTED_STATUSES = frozenset({"blocked"})


def _frontmatter_field(text: str, key: str) -> str:
    m = re.search(rf"^{re.escape(key)}:[ \t]*([^\n]*)$", text, re.MULTILINE)
    return m.group(1).strip().lower() if m else ""


def _set_frontmatter_field(text: str, key: str, value: str) -> str:
    pattern = re.compile(rf"^({re.escape(key)}:)[^\n]*$", re.MULTILINE)
    if pattern.search(text):
        return pattern.sub(rf"\1 {value}", text, count=1)

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
    dest = target or "(top of org — no higher reviewer)"
    entry = (
        f"\n### {now()} — Guardrail escalation ({role} → {dest})\n"
        f"origin: {OUTPUT_GUARDRAIL_ORIGIN}\n"
        f"Exhausted {max_retries} retries; OUTPUT guardrail still tripping: {feedback}\n"
        f"Escalating to {dest} for review.\n"
    )

    def _transform(text: str) -> str:
        if target:
            text = _set_frontmatter_field(text, "assignee", target)
            if _frontmatter_field(text, "status") not in HALTED_STATUSES:
                text = _set_frontmatter_field(text, "status", "in_review")
            text = _set_frontmatter_field(text, "updated", now())
        return text + entry

    _fl.locked_update_text(ticket_path, _transform, missing_ok=False)


def guardrail_dispatch(
    ticket_path: Path,
    run_agent: Callable[[GuardrailContext, int], str],
    *,
    routing_path: Path | None = DEFAULT_ROUTING,
    board_dir: Path = DEFAULT_BOARD,
    guardrails_dir: Path = _runner.DEFAULT_GUARDRAILS_DIR,
    max_retries: int = DEFAULT_MAX_RETRIES,
    gate_open: bool = False,
    now: Callable[[], str] = _today,
) -> DispatchResult:
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


    ok, feedback = _runner.run_input(role, ctx, guardrails_dir)
    if not ok:
        return DispatchResult(
            ticket_id=ctx.ticket_id,
            role=role,
            accepted=False,
            outcome="input_rejected",
            feedback=feedback,
        )


    feedback_log: list[str] = []
    last_feedback = ""
    for attempt in range(max_retries + 1):
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


@dataclass
class WaveScreenResult:

    accepted: list[str] = field(default_factory=list)
    rejected: list[dict] = field(default_factory=list)

    @property
    def all_accepted(self) -> bool:
        return not self.rejected

    @property
    def rejected_ids(self) -> list[str]:
        return [r["ticket_id"] for r in self.rejected]


def screen_wave_inputs(
    ticket_paths: list[Path],
    *,
    routing_path: Path | None = DEFAULT_ROUTING,
    board_dir: Path = DEFAULT_BOARD,
    guardrails_dir: Path = _runner.DEFAULT_GUARDRAILS_DIR,
    gate_open_ids: set[str] | None = None,
) -> WaveScreenResult:
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

                "reroute_to": ctx.ticket_dept or None,
            })
    return result


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description='guardrail_dispatch.py — INPUT/OUTPUT guardrail dispatch wrapper (DAS-1471)', formatter_class=argparse.RawDescriptionHelpFormatter
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
