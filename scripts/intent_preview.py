#!/usr/bin/env python3
"""intent_preview.py — Agent Intent Preview.

Shows WHAT an agent plans to do BEFORE execution — defeating the "black-box wave"
anxiety (human trust is the weakest assessed dimension, 55/100). Given a planned
dispatch (or a board ticket), it renders the agent, model, plan summary, and
declared tools, and — by running the plan through the never-auto-approve matchers
(config/risk_taxonomy.yaml) — tells the operator up front whether it REQUIRES human
approval (QONUN-5) before it may run.

A dispatch plan:
    {ticket_id, role, model, summary, ticket_type?, stage?, labels?[], paths?[], planned_tools?[]}

Usage:
    python3 scripts/intent_preview.py --plan-file plan.json
    python3 scripts/intent_preview.py --ticket DAS-1311
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import check_never_auto_approve as nap
from _paths import ROOT

try:
    import yaml
except ImportError:  # pragma: no cover - environment guard
    sys.stderr.write("PyYAML required: pip install pyyaml\n")
    sys.exit(2)


def build_intent(plan: dict, taxonomy: dict) -> dict:
    """Classify a planned dispatch: which never-auto-approve categories it hits and
    therefore whether it needs human approval before execution."""
    never = taxonomy.get("never_auto_approve", [])
    matchers = taxonomy.get("matchers", {}) or {}
    fm = {k: plan.get(k) for k in ("ticket_type", "stage", "labels", "paths")}
    categories = [c for c in never if nap.matches_category(fm, matchers.get(c, {}))]
    forced = plan.get("_fail_closed")
    if forced:  # fail-CLOSED input (unparseable/smuggled) -> human-required, never auto
        categories = [forced, *categories]
    tools = plan.get("planned_tools", plan.get("tools", [])) or []
    return {
        "ticket": str(plan.get("ticket_id", "?")),
        "agent": str(plan.get("role", "?")),
        "model": str(plan.get("model", "?")),
        "summary": str(plan.get("summary", "")),
        "tools": [str(t) for t in tools],
        "never_auto_approve_categories": categories,
        "needs_human_approval": bool(categories),
    }


def render_intent(intent: dict) -> str:
    lines = [
        f"Intent preview — {intent['ticket']}",
        f"  agent : {intent['agent']} ({intent['model']})",
        f"  plan  : {intent['summary'] or '(no summary)'}",
        f"  tools : {', '.join(intent['tools']) if intent['tools'] else 'none declared'}",
    ]
    if intent["needs_human_approval"]:
        cats = ", ".join(intent["never_auto_approve_categories"])
        lines.append(f"  gate  : REQUIRES HUMAN APPROVAL (QONUN-5) -> {cats}")
    else:
        lines.append("  gate  : auto-approvable (no never-auto-approve category)")
    return "\n".join(lines)


def ticket_plan(board: Path, ticket_id: str) -> dict | None:
    tickets_dir = board / "tickets"
    matches = sorted(tickets_dir.glob(f"{ticket_id}-*.md")) + sorted(tickets_dir.glob(f"{ticket_id}.md"))
    if not matches:
        return None
    fm = nap.parse_frontmatter(matches[0].read_text(encoding="utf-8", errors="ignore"))
    if fm is None:
        # fail-CLOSED, exactly like check_never_auto_approve: a ticket whose
        # frontmatter is unparseable/smuggled must preview as human-required.
        return {
            "ticket_id": ticket_id, "role": "(unrouted)", "model": "?",
            "summary": "(frontmatter unparseable or fence-smuggled)",
            "_fail_closed": "unparseable-or-smuggled-frontmatter",
        }
    return {
        "ticket_id": fm.get("id", ticket_id),
        "role": fm.get("assignee") or "(unrouted)",
        "model": fm.get("model", "(per allocation)"),
        "summary": fm.get("title", ""),
        "ticket_type": fm.get("ticket_type"),
        "stage": fm.get("stage"),
        "labels": fm.get("labels"),
        "paths": fm.get("paths"),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--plan-file", type=Path, default=None)
    ap.add_argument("--ticket", default=None)
    ap.add_argument("--board", type=Path, default=ROOT / "board")
    ap.add_argument("--config", type=Path, default=ROOT / "config" / "risk_taxonomy.yaml")
    args = ap.parse_args(argv)

    if not args.config.is_file():
        sys.stderr.write(f"ERROR: risk taxonomy not found: {args.config}\n")
        return 2
    taxonomy = yaml.safe_load(args.config.read_text()) or {}

    if args.plan_file:
        if not args.plan_file.is_file():
            sys.stderr.write(f"ERROR: plan file not found: {args.plan_file}\n")
            return 2
        try:
            plan = json.loads(args.plan_file.read_text())
        except json.JSONDecodeError as exc:
            sys.stderr.write(f"ERROR: invalid plan JSON: {exc}\n")
            return 2
        if not isinstance(plan, dict):
            sys.stderr.write("ERROR: plan must be a JSON object\n")
            return 2
    elif args.ticket:
        plan = ticket_plan(args.board, args.ticket)
        if plan is None:
            sys.stderr.write(f"ERROR: ticket not found on the board: {args.ticket}\n")
            return 2
    else:
        sys.stderr.write("ERROR: provide --plan-file or --ticket\n")
        return 2

    print(render_intent(build_intent(plan, taxonomy)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
