#!/usr/bin/env python3
"""tests/test_check_dependency_graph.py — Phase 3 dependency graph (ADR-0016 / ADR-0002)."""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import check_dependency_graph as dg  # noqa: E402  (import after path manipulation)


def _board(tmp_path: Path, *tickets: tuple[str, str, str]) -> Path:
    """tickets: (id, depends_on_inline, zone). '' omits the field."""
    bdir = tmp_path / "board"
    bdir.mkdir(exist_ok=True)
    for tid, deps, zone in tickets:
        fm = f"---\nid: {tid}\nstatus: todo\nauthor: ceo\n"
        if deps:
            fm += f"depends_on: {deps}\n"
        if zone != "_OMIT_":
            fm += f"zone: {zone}\n"
        fm += "---\n\n## Description\nx\n"
        (bdir / f"{tid}-t.md").write_text(fm, encoding="utf-8")
    return bdir


def _run(board: Path) -> int:
    return dg.main(["--board", str(board)])


def test_empty_board_passes(tmp_path):
    assert _run(_board(tmp_path, ("DAS-1", "", "_OMIT_"))) == 0


def test_valid_dependency_passes(tmp_path):
    assert _run(_board(tmp_path, ("DAS-1", "", "_OMIT_"), ("DAS-2", "[DAS-1]", "_OMIT_"))) == 0


def test_dangling_dependency_fails(tmp_path):
    assert _run(_board(tmp_path, ("DAS-2", "[DAS-9999]", "_OMIT_"))) == 1


def test_self_cycle_fails(tmp_path):
    assert _run(_board(tmp_path, ("DAS-1", "[DAS-1]", "_OMIT_"))) == 1


def test_two_node_cycle_fails(tmp_path):
    assert _run(_board(tmp_path, ("DAS-1", "[DAS-2]", "_OMIT_"), ("DAS-2", "[DAS-1]", "_OMIT_"))) == 1


def test_three_node_cycle_fails(tmp_path):
    board = _board(
        tmp_path,
        ("DAS-1", "[DAS-2]", "_OMIT_"),
        ("DAS-2", "[DAS-3]", "_OMIT_"),
        ("DAS-3", "[DAS-1]", "_OMIT_"),
    )
    assert _run(board) == 1


def test_dag_diamond_passes(tmp_path):
    board = _board(
        tmp_path,
        ("DAS-1", "", "_OMIT_"),
        ("DAS-2", "[DAS-1]", "_OMIT_"),
        ("DAS-3", "[DAS-1]", "_OMIT_"),
        ("DAS-4", "[DAS-2, DAS-3]", "_OMIT_"),
    )
    assert _run(board) == 0


def test_valid_zone_passes(tmp_path):
    assert _run(_board(tmp_path, ("DAS-1", "", "apps/web"))) == 0


def test_empty_zone_fails(tmp_path):
    assert _run(_board(tmp_path, ("DAS-1", "", ""))) == 1


def test_missing_board_dir_exit_2(tmp_path):
    assert dg.main(["--board", str(tmp_path / "nope")]) == 2


def test_real_repo_passes():
    assert dg.main([]) == 0


# --- producer / consumer checks (DAS-1468) ---

def _board_pc(tmp_path: Path, *tickets: tuple) -> Path:
    """Extended ticket builder supporting produces: and consumes: fields.

    tickets: (id, depends_on_inline, zone, produces, consumes[, goal])
      zone     : '' = present-and-empty (validator error), '_OMIT_' = absent
      produces : '' = absent
      consumes : '' = absent
      goal     : '' = absent
    """
    bdir = tmp_path / "board"
    bdir.mkdir(exist_ok=True)
    for item in tickets:
        tid: str = item[0]
        deps: str = item[1]
        zone: str = item[2]
        produces: str = item[3]
        consumes: str = item[4]
        goal: str = item[5] if len(item) > 5 else ""
        fm = f"---\nid: {tid}\nstatus: todo\nauthor: ceo\n"
        if deps:
            fm += f"depends_on: {deps}\n"
        if zone != "_OMIT_":
            fm += f"zone: {zone}\n"
        if produces:
            fm += f"produces: {produces}\n"
        if consumes:
            fm += f"consumes: {consumes}\n"
        if goal:
            fm += f"goal: {goal}\n"
        fm += "---\n\n## Description\nx\n"
        (bdir / f"{tid}-t.md").write_text(fm, encoding="utf-8")
    return bdir


def test_missing_producer_fails(tmp_path):
    """Consumer declares consumes: foo but no ticket on the board produces it."""
    board = _board_pc(
        tmp_path,
        ("DAS-1", "", "_OMIT_", "", "foo"),
    )
    assert _run(board) == 1


def test_matched_producer_passes(tmp_path):
    """Producer declares produces: foo, consumer declares consumes: foo — no violation."""
    board = _board_pc(
        tmp_path,
        ("DAS-1", "", "_OMIT_", "foo", ""),
        ("DAS-2", "[DAS-1]", "_OMIT_", "", "foo"),
    )
    assert _run(board) == 0


def test_disconnected_pc_goal_fails(tmp_path):
    """Tickets sharing a goal that uses produces/consumes but have no depends_on link."""
    board = _board_pc(
        tmp_path,
        # DAS-1 produces foo (goal g1), DAS-2 consumes foo (goal g1) but no dep
        ("DAS-1", "", "_OMIT_", "foo", "", "g1"),
        ("DAS-2", "", "_OMIT_", "", "foo", "g1"),
    )
    # producer/consumer match is satisfied (DAS-1 produces foo),
    # but the graph is disconnected within goal g1 → exit 1
    assert _run(board) == 1


def test_board_without_pc_fields_passes(tmp_path):
    """CI-safe / dormant: a board with no produces:/consumes: still passes."""
    board = _board(
        tmp_path,
        ("DAS-1", "", "_OMIT_"),
        ("DAS-2", "[DAS-1]", "_OMIT_"),
    )
    assert _run(board) == 0


# --- skill-rule guards (the runtime same-zone / dep-blocked rules live in the skill) ---

def _cycle_skill_flat() -> str:
    p = REPO_ROOT / ".claude" / "skills" / "daslab-cycle" / "SKILL.md"
    return " ".join(p.read_text(encoding="utf-8").lower().split())


def test_skill_reads_zone_in_correctness_guard():
    assert "zone:" in _cycle_skill_flat()


def test_skill_keeps_dep_blocked_rule():
    skill = _cycle_skill_flat()
    assert "depends_on" in skill and "dep-blocked" in skill
