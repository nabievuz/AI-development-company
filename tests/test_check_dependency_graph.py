#!/usr/bin/env python3

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import check_dependency_graph as dg
import wave_planner as wp


def _board(tmp_path: Path, *tickets: tuple[str, str, str]) -> Path:
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


def _board_pc(tmp_path: Path, *tickets: tuple) -> Path:
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
    board = _board_pc(
        tmp_path,
        ("DAS-1", "", "_OMIT_", "", "foo"),
    )
    assert _run(board) == 1


def test_matched_producer_passes(tmp_path):
    board = _board_pc(
        tmp_path,
        ("DAS-1", "", "_OMIT_", "foo", ""),
        ("DAS-2", "[DAS-1]", "_OMIT_", "", "foo"),
    )
    assert _run(board) == 0


def test_disconnected_pc_goal_fails(tmp_path):
    board = _board_pc(
        tmp_path,

        ("DAS-1", "", "_OMIT_", "foo", "", "g1"),
        ("DAS-2", "", "_OMIT_", "", "foo", "g1"),
    )


    assert _run(board) == 1


def test_board_without_pc_fields_passes(tmp_path):
    board = _board(
        tmp_path,
        ("DAS-1", "", "_OMIT_"),
        ("DAS-2", "[DAS-1]", "_OMIT_"),
    )
    assert _run(board) == 0


_PLANNER_ORG = wp.OrgModel(role_models={"backend-eng-1": "sonnet", "backend-eng-2": "sonnet"})


def _planner_ticket(ticket_id, *, zone, depends_on=(), status="todo", role="backend-eng-1"):
    return wp.Ticket(
        ticket_id=ticket_id, role=role, status=status, zone=zone, depends_on=depends_on
    )


def test_planner_reads_zone_in_the_correctness_guard():
    a = _planner_ticket("DAS-1", zone="scripts")
    b = _planner_ticket("DAS-2", zone="scripts", role="backend-eng-2")
    plan = wp.plan_wave([a, b], _PLANNER_ORG, [])
    assert [pt.ticket_id for pt in plan.dispatch] == ["DAS-1"]
    assert [(r.ticket_id, r.reason) for r in plan.refused] == [
        ("DAS-2", wp.RefusalReason.ZONE_CONFLICT)
    ]


def test_planner_honours_zones_already_occupied_by_a_running_wave():
    plan = wp.plan_wave([_planner_ticket("DAS-1", zone="scripts")], _PLANNER_ORG, ["scripts"])
    assert plan.dispatch == ()
    assert plan.refused[0].reason is wp.RefusalReason.ZONE_CONFLICT


def test_planner_keeps_the_dep_blocked_rule():
    blocker = _planner_ticket("DAS-1", zone="a")
    blocked = _planner_ticket("DAS-2", zone="b", depends_on=("DAS-1",), role="backend-eng-2")
    plan = wp.plan_wave([blocker, blocked], _PLANNER_ORG, [])
    assert [pt.ticket_id for pt in plan.dispatch] == ["DAS-1"]
    refusal = next(r for r in plan.refused if r.ticket_id == "DAS-2")
    assert refusal.reason is wp.RefusalReason.UNMET_DEPENDENCY
    assert "DAS-1" in refusal.detail


def test_planner_dep_guard_is_not_inverted():
    done_blocker = _planner_ticket("DAS-1", zone="a", status="done")
    blocked = _planner_ticket("DAS-2", zone="b", depends_on=("DAS-1",), role="backend-eng-2")
    plan = wp.plan_wave([done_blocker, blocked], _PLANNER_ORG, [])
    assert [pt.ticket_id for pt in plan.dispatch] == ["DAS-2"]


def test_planner_refuses_an_unknown_dependency():
    blocked = _planner_ticket("DAS-2", zone="b", depends_on=("DAS-404",))
    plan = wp.plan_wave([blocked], _PLANNER_ORG, [])
    assert plan.dispatch == ()
    assert plan.refused[0].reason is wp.RefusalReason.UNMET_DEPENDENCY
