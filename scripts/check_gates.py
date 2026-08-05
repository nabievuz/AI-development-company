#!/usr/bin/env python3


from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from _paths import ROOT

ACTIONABLE_STATUSES: frozenset[str] = frozenset({"todo", "in_progress"})


_STAGE_NUM_RE = re.compile(r"Stage\s+([1-6])", re.IGNORECASE)
_GATE_NUM_RE = re.compile(r"GATE-([1-6])", re.IGNORECASE)


_REPO_ROOT = ROOT


_FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_KV_RE = re.compile(r"^([a-zA-Z_][a-zA-Z0-9_-]*):[^\S\n]*(.*?)[^\S\n]*$", re.MULTILINE)


def parse_frontmatter(text: str) -> dict[str, str] | None:
    m = _FM_RE.match(text)
    if not m:
        return None
    block = m.group(1)
    data: dict[str, str] = {}
    for key, value in _KV_RE.findall(block):

        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            value = value[1:-1]
        data[key] = value
    return data


def load_tickets(board_dir: Path) -> list[tuple[Path, dict[str, str]]]:
    results: list[tuple[Path, dict[str, str]]] = []
    for path in sorted(board_dir.glob("DAS-*.md")):
        text = path.read_text(encoding="utf-8")
        fm = parse_frontmatter(text)
        results.append((path, fm if fm is not None else {}))
    return results


def extract_stage_number(title: str) -> int | None:
    sm = _STAGE_NUM_RE.search(title)
    gm = _GATE_NUM_RE.search(title)
    if sm and gm:
        stage = int(sm.group(1))
        gate = int(gm.group(1))
        if stage == gate:
            return stage
    return None


def is_gate_epic(fm: dict[str, str]) -> bool:
    parent = fm.get("parent", "").strip()
    if parent:
        return False
    title = fm.get("title", "")
    return extract_stage_number(title) is not None


GateMap = dict[int, str]
GoalGates = dict[str, GateMap]


def build_gate_map(tickets: list[tuple[Path, dict[str, str]]]) -> GoalGates:
    goal_gates: GoalGates = {}
    for _path, fm in tickets:
        if not is_gate_epic(fm):
            continue
        goal = fm.get("goal", "").strip()
        if not goal:
            continue
        title = fm.get("title", "")
        stage = extract_stage_number(title)
        if stage is None:
            continue
        status = fm.get("status", "").strip()
        goal_gates.setdefault(goal, {})[stage] = status
    return goal_gates


def check_gates(
    tickets: list[tuple[Path, dict[str, str]]],
    goal_gates: GoalGates | None = None,
) -> list[str]:
    if goal_gates is None:
        goal_gates = build_gate_map(tickets)


    by_id: dict[str, dict[str, str]] = {}
    for _path, fm in tickets:
        tid = fm.get("id", "").strip()
        if tid:
            by_id[tid] = fm

    violations: list[str] = []

    for _path, fm in tickets:
        status = fm.get("status", "").strip()
        if status not in ACTIONABLE_STATUSES:
            continue

        parent_id = fm.get("parent", "").strip()
        if not parent_id:

            continue

        goal = fm.get("goal", "").strip()
        ticket_id = fm.get("id", _path.name)


        stage: int | None = None
        cursor_id = parent_id
        visited: set[str] = set()
        while cursor_id and cursor_id not in visited:
            visited.add(cursor_id)
            parent_fm = by_id.get(cursor_id)
            if parent_fm is None:
                break
            title = parent_fm.get("title", "")
            candidate = extract_stage_number(title)
            if candidate is not None:
                stage = candidate
                break
            cursor_id = parent_fm.get("parent", "").strip()

        if stage is None or stage < 2:

            continue

        prior_stage = stage - 1
        gates_for_goal = goal_gates.get(goal, {})
        prior_status = gates_for_goal.get(prior_stage)

        if prior_status is None:

            continue

        if prior_status != "done":
            violations.append(
                f"{ticket_id}: actionable (status={status!r}) at stage {stage} "
                f"but GATE-{prior_stage} for goal '{goal}' is '{prior_status}' "
                f"(must be 'done' first)"
            )

    return violations


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description='check_gates.py — enforce AADL gate order on the DasLab board',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--board",
        type=Path,
        default=_REPO_ROOT / "board" / "tickets",
        help="Path to the board/tickets/ directory (default: auto-detected from repo root)",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    board_dir: Path = args.board
    if not board_dir.is_dir():
        print(f"ERROR: board directory not found: {board_dir}", file=sys.stderr)
        return 2

    try:
        tickets = load_tickets(board_dir)
    except OSError as exc:
        print(f"ERROR reading board tickets: {exc}", file=sys.stderr)
        return 2

    violations = check_gates(tickets)

    if violations:
        print(
            f"check_gates: {len(violations)} gate-order violation(s) found:\n",
            file=sys.stderr,
        )
        for v in violations:
            print(f"  FAIL  {v}", file=sys.stderr)
        return 1

    print(f"check_gates: OK — {len(tickets)} ticket(s) checked, 0 gate-order violations.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
