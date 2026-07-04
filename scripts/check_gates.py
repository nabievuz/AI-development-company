#!/usr/bin/env python3
"""check_gates.py — enforce AADL gate order on the DasLab board.

Reads every ``board/tickets/DAS-*.md`` file, identifies stage-gate epics
(top-level tickets whose title contains ``Stage N`` / ``GATE-N``), then flags
any ticket that is *actionable* (status: ``todo`` or ``in_progress``) whose
parent stage epic is at stage N while the preceding gate-epic (stage N-1) for
the same project goal is **not** ``done``.

AADL gate order (QONUN 2 / governance/policies/ai-agent-lifecycle.md):

    Stage 1 (Planning)  → GATE-1
    Stage 2 (Design)    → GATE-2
    Stage 3 (Dev)       → GATE-3
    Stage 4 (Testing)   → GATE-4
    Stage 5 (Deploy)    → GATE-5
    Stage 6 (Maint.)    → GATE-6

A ticket at stage N may be actionable only when GATE-(N-1) is done.

Usage::

    python3 scripts/check_gates.py [--board <path>]

Exit codes: 0 = no violations, 1 = violations found, 2 = usage/IO error.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from _paths import ROOT

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ACTIONABLE_STATUSES: frozenset[str] = frozenset({"todo", "in_progress"})

# Regex to extract the stage number from a gate-epic title.
# Matches titles like:
#   "<project> — Stage 3: Development build (GATE-3)"
#   "<project> — Stage 1: Close GATE-1 (Planning)"
_STAGE_NUM_RE = re.compile(r"Stage\s+([1-6])", re.IGNORECASE)
_GATE_NUM_RE = re.compile(r"GATE-([1-6])", re.IGNORECASE)

# Repo root is two levels up from this script (scripts/ -> root)
_REPO_ROOT = ROOT


# ---------------------------------------------------------------------------
# Frontmatter parser — lightweight, no external deps
# ---------------------------------------------------------------------------

_FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_KV_RE = re.compile(r"^([a-zA-Z_][a-zA-Z0-9_-]*):[^\S\n]*(.*?)[^\S\n]*$", re.MULTILINE)


def parse_frontmatter(text: str) -> dict[str, str] | None:
    """Return key→value dict from YAML frontmatter, or None if absent/malformed."""
    m = _FM_RE.match(text)
    if not m:
        return None
    block = m.group(1)
    data: dict[str, str] = {}
    for key, value in _KV_RE.findall(block):
        # Strip inline YAML quotes if present
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            value = value[1:-1]
        data[key] = value
    return data


# ---------------------------------------------------------------------------
# Ticket loader
# ---------------------------------------------------------------------------


def load_tickets(board_dir: Path) -> list[tuple[Path, dict[str, str]]]:
    """Return list of (path, frontmatter) for every DAS-*.md in *board_dir*."""
    results: list[tuple[Path, dict[str, str]]] = []
    for path in sorted(board_dir.glob("DAS-*.md")):
        text = path.read_text(encoding="utf-8")
        fm = parse_frontmatter(text)
        results.append((path, fm if fm is not None else {}))
    return results


# ---------------------------------------------------------------------------
# Gate-epic identification
# ---------------------------------------------------------------------------


def extract_stage_number(title: str) -> int | None:
    """Return the AADL stage number (1–6) from a gate-epic title, or None.

    A gate epic must mention BOTH ``Stage N`` and ``GATE-N`` in its title;
    both numbers must agree.  This prevents false positives from tickets that
    happen to mention a gate in passing.
    """
    sm = _STAGE_NUM_RE.search(title)
    gm = _GATE_NUM_RE.search(title)
    if sm and gm:
        stage = int(sm.group(1))
        gate = int(gm.group(1))
        if stage == gate:
            return stage
    return None


def is_gate_epic(fm: dict[str, str]) -> bool:
    """Return True if this ticket is a top-level AADL stage-gate epic."""
    parent = fm.get("parent", "").strip()
    if parent:
        return False  # gate epics are always top-level
    title = fm.get("title", "")
    return extract_stage_number(title) is not None


# ---------------------------------------------------------------------------
# Core validation logic
# ---------------------------------------------------------------------------

GateMap = dict[int, str]  # stage_number -> status (e.g. "done")
GoalGates = dict[str, GateMap]  # goal -> GateMap


def build_gate_map(tickets: list[tuple[Path, dict[str, str]]]) -> GoalGates:
    """Build a map of goal → {stage_number → gate_status} from gate epics."""
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
    """Return human-readable violation strings for out-of-order actionable tickets.

    A violation fires when:
    - The ticket is actionable (todo | in_progress)
    - The ticket has a ``parent`` (i.e. it is a subtask, not a gate epic itself)
    - The parent belongs to stage N (identified by the parent's goal-gate map)
    - The gate epic for stage N-1 in the same ``goal`` is not ``done``
    - N >= 2 (Stage 1 has no predecessor)

    Parameters
    ----------
    tickets:
        List of (path, frontmatter) pairs as returned by ``load_tickets``.
    goal_gates:
        Pre-built gate map (pass for unit tests with synthetic data).
        If None, ``build_gate_map`` is called on *tickets*.
    """
    if goal_gates is None:
        goal_gates = build_gate_map(tickets)

    # Index tickets by ID for parent look-up
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
            # Top-level epic — handled separately if needed; skip child check
            continue

        goal = fm.get("goal", "").strip()
        ticket_id = fm.get("id", _path.name)

        # Determine which stage this ticket belongs to by looking at the parent.
        # Walk up the parent chain until we hit a gate epic (or run out).
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
            # Stage 1 has no predecessor; or stage could not be determined.
            continue

        prior_stage = stage - 1
        gates_for_goal = goal_gates.get(goal, {})
        prior_status = gates_for_goal.get(prior_stage)

        if prior_status is None:
            # No gate epic recorded for the prior stage — cannot verify; skip.
            continue

        if prior_status != "done":
            violations.append(
                f"{ticket_id}: actionable (status={status!r}) at stage {stage} "
                f"but GATE-{prior_stage} for goal '{goal}' is '{prior_status}' "
                f"(must be 'done' first)"
            )

    return violations


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=__doc__,
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
    """Entry point; returns an exit code."""
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
