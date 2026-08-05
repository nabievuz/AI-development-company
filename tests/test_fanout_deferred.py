#!/usr/bin/env python3

from __future__ import annotations

import re
import sys
from dataclasses import replace
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import check_dependency_graph as dg
import wave_planner as wp
from board_lint import parse_frontmatter
from fanout import emit_fanout, is_actionable

_PARENT_META = {
    "author": "senior-pm",
    "dept": "engineering",
    "priority": "p1",
    "goal": "test-goal",
    "zone": "daslab-cycle",
}

_THREE_CHILDREN = [
    {"title": "Child A", "assignee": "backend-eng-1", "payload": "Secret payload A"},
    {"title": "Child B", "assignee": "backend-eng-2", "payload": "Secret payload B"},
    {"title": "Child C", "assignee": "backend-eng-1", "payload": "Secret payload C"},
]

_SYNTHESIS_META = {
    "title": "Aggregate A B C",
    "assignee": "backend-em",
    "payload": "Aggregate results from child tickets.",
}

_DAS_RE = re.compile(r"\bDAS-\d+\b")


def _emit(board_dir: Path, children=None, synthesis=None):
    return emit_fanout(
        board_dir=board_dir,
        parent_id="DAS-9000",
        parent_meta=_PARENT_META,
        children_payloads=children if children is not None else _THREE_CHILDREN,
        synthesis_meta=synthesis if synthesis is not None else _SYNTHESIS_META,
        date="2026-07-03",
    )


def _load_all_fm(board_dir: Path) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for md in sorted(board_dir.glob("DAS-*.md")):
        fm = parse_frontmatter(md.read_text(encoding="utf-8"))
        if fm and fm.get("id"):
            result[fm["id"]] = fm
    return result


def _ticket_text(board_dir: Path, ticket_id: str) -> str:
    for md in sorted(board_dir.glob("DAS-*.md")):
        text = md.read_text(encoding="utf-8")
        if re.search(rf"^id:\s*{re.escape(ticket_id)}\s*$", text, re.MULTILINE):
            return text
    raise FileNotFoundError(f"No ticket file found for {ticket_id} in {board_dir}")


def test_emit_produces_n_children_plus_one_synthesis(tmp_path):
    child_ids, synthesis_id = _emit(tmp_path, children=_THREE_CHILDREN[:2])
    assert len(child_ids) == 2
    assert synthesis_id.startswith("DAS-")
    fms = _load_all_fm(tmp_path)
    for cid in child_ids:
        assert cid in fms, f"child ticket {cid} not found on disk"
    assert synthesis_id in fms, "synthesis ticket not found on disk"

    assert len(list(tmp_path.glob("DAS-*.md"))) == 3


def test_synthesis_has_defer_true(tmp_path):
    _, synthesis_id = _emit(tmp_path)
    fms = _load_all_fm(tmp_path)
    assert fms[synthesis_id].get("defer", "").lower() == "true"


def test_synthesis_depends_on_all_children(tmp_path):
    child_ids, synthesis_id = _emit(tmp_path)
    fms = _load_all_fm(tmp_path)
    dep_raw = fms[synthesis_id].get("depends_on", "")
    dep_ids = set(_DAS_RE.findall(dep_raw))
    assert dep_ids == set(child_ids), (
        f"synthesis depends_on {dep_ids!r} != children {set(child_ids)!r}"
    )


def test_children_have_no_depends_on(tmp_path):
    child_ids, _ = _emit(tmp_path)
    fms = _load_all_fm(tmp_path)
    for cid in child_ids:
        dep_raw = fms[cid].get("depends_on", "")
        assert not dep_raw, f"child {cid} unexpectedly has depends_on: {dep_raw!r}"


def test_children_have_parent_set(tmp_path):
    child_ids, _ = _emit(tmp_path)
    fms = _load_all_fm(tmp_path)
    for cid in child_ids:
        assert fms[cid].get("parent", "") == "DAS-9000"


def test_synthesis_has_parent_set(tmp_path):
    _, synthesis_id = _emit(tmp_path)
    fms = _load_all_fm(tmp_path)
    assert fms[synthesis_id].get("parent", "") == "DAS-9000"


def test_private_payloads_isolated_from_siblings(tmp_path):
    child_ids, synthesis_id = _emit(tmp_path, children=_THREE_CHILDREN)
    id_to_text: dict[str, str] = {
        cid: _ticket_text(tmp_path, cid) for cid in child_ids + [synthesis_id]
    }
    payloads = {
        child_ids[0]: "Secret payload A",
        child_ids[1]: "Secret payload B",
        child_ids[2]: "Secret payload C",
    }
    for owner_id, payload in payloads.items():

        assert payload in id_to_text[owner_id], (
            f"{owner_id} is missing its own payload"
        )

        for other_id, other_text in id_to_text.items():
            if other_id != owner_id:
                assert payload not in other_text, (
                    f"payload of {owner_id!r} leaked into {other_id!r}"
                )


def test_synthesis_body_contains_no_raw_child_payloads(tmp_path):
    child_ids, synthesis_id = _emit(tmp_path, children=_THREE_CHILDREN)
    synth_text = _ticket_text(tmp_path, synthesis_id)
    for child in _THREE_CHILDREN:
        assert child["payload"] not in synth_text, (
            f"synthesis contains raw child payload: {child['payload']!r}"
        )


def test_n_is_runtime_determined(tmp_path):
    b1 = tmp_path / "b1"
    b1.mkdir()
    ids1, _ = emit_fanout(
        board_dir=b1,
        parent_id="DAS-9100",
        parent_meta=_PARENT_META,
        children_payloads=[_THREE_CHILDREN[0]],
        synthesis_meta=_SYNTHESIS_META,
        date="2026-07-03",
    )
    assert len(ids1) == 1

    b5 = tmp_path / "b5"
    b5.mkdir()
    ids5, _ = emit_fanout(
        board_dir=b5,
        parent_id="DAS-9200",
        parent_meta=_PARENT_META,
        children_payloads=[
            {"title": f"Chunk {i}", "assignee": "backend-eng-1", "payload": f"data-{i}"}
            for i in range(5)
        ],
        synthesis_meta=_SYNTHESIS_META,
        date="2026-07-03",
    )
    assert len(ids5) == 5


def test_empty_children_raises(tmp_path):
    with pytest.raises(ValueError, match="non-empty"):
        _emit(tmp_path, children=[])


def test_synthesis_dep_blocked_while_all_children_todo(tmp_path):
    child_ids, synthesis_id = _emit(tmp_path, children=_THREE_CHILDREN[:2])
    fms = _load_all_fm(tmp_path)
    assert not is_actionable(fms[synthesis_id], fms), (
        "synthesis must be dep-blocked while children are todo"
    )


def test_synthesis_blocked_when_one_child_remains_open(tmp_path):
    child_ids, synthesis_id = _emit(tmp_path, children=_THREE_CHILDREN)
    fms = _load_all_fm(tmp_path)
    fms[child_ids[0]]["status"] = "done"
    fms[child_ids[1]]["status"] = "done"

    assert not is_actionable(fms[synthesis_id], fms), (
        "synthesis must be dep-blocked while even one child is not done"
    )


def test_synthesis_actionable_once_all_children_done(tmp_path):
    child_ids, synthesis_id = _emit(tmp_path, children=_THREE_CHILDREN[:2])
    fms = _load_all_fm(tmp_path)
    for cid in child_ids:
        fms[cid]["status"] = "done"
    assert is_actionable(fms[synthesis_id], fms), (
        "synthesis must be actionable when all children are done"
    )


def test_children_are_immediately_actionable(tmp_path):
    child_ids, _ = _emit(tmp_path, children=_THREE_CHILDREN[:2])
    fms = _load_all_fm(tmp_path)
    for cid in child_ids:
        assert is_actionable(fms[cid], fms), f"{cid} must be immediately actionable"


def test_defer_hard_guard_fires_independently():
    fm_synth = {
        "id": "DAS-9999",
        "status": "todo",
        "defer": "true",
        "depends_on": "[DAS-9998]",
    }
    fm_child_open = {"id": "DAS-9998", "status": "in_progress"}
    fms_by_id = {"DAS-9999": fm_synth, "DAS-9998": fm_child_open}


    assert not is_actionable(fm_synth, fms_by_id)


    fm_child_open["status"] = "done"
    assert is_actionable(fm_synth, fms_by_id)


def test_defer_true_with_no_deps_is_actionable():
    fm = {"id": "DAS-9999", "status": "todo", "defer": "true", "depends_on": ""}
    assert is_actionable(fm, {"DAS-9999": fm})


def test_is_actionable_respects_non_todo_status():
    for bad_status in ("done", "blocked", "in_review", "backlog"):
        fm = {"id": "DAS-1", "status": bad_status}
        assert not is_actionable(fm, {"DAS-1": fm}), (
            f"expected not-actionable for status={bad_status!r}"
        )


def test_emitted_fanout_passes_dep_graph(tmp_path):
    _emit(tmp_path)
    assert dg.main(["--board", str(tmp_path)]) == 0


def test_defer_true_with_empty_depends_on_fails_dep_graph(tmp_path):
    bad = tmp_path / "DAS-1-bad-deferred.md"
    bad.write_text(
        "---\nid: DAS-1\ntitle: Bad deferred\nstatus: todo\nassignee: qa-eng\n"
        "author: ceo\ndept: engineering\npriority: p1\n"
        "created: 2026-07-03\nupdated: 2026-07-03\ndefer: true\n---\n\n## Log\n",
        encoding="utf-8",
    )
    assert dg.main(["--board", str(tmp_path)]) == 1


def test_real_repo_board_passes_after_extension():
    assert dg.main([]) == 0


_FANOUT_ORG = wp.OrgModel(
    role_models={"backend-eng-1": "sonnet", "backend-eng-2": "sonnet", "backend-em": "opus"}
)


def _planner_board(board_dir: Path):
    return wp.load_board_tickets(board_dir)


def test_planner_refuses_a_deferred_ticket(tmp_path):
    _emit(tmp_path)
    tickets = _planner_board(tmp_path)
    deferred = [t for t in tickets if t.deferred]
    assert deferred, "fanout must emit a deferred synthesis ticket"

    plan = wp.plan_wave(tickets, _FANOUT_ORG, [])
    dispatched = {pt.ticket_id for pt in plan.dispatch}
    for ticket in deferred:
        assert ticket.ticket_id not in dispatched
    reasons = {r.ticket_id: r.reason for r in plan.refused}
    for ticket in deferred:
        assert reasons[ticket.ticket_id] is wp.RefusalReason.DEFERRED


def test_planner_dispatches_the_synthesis_ticket_once_defer_is_cleared(tmp_path):
    _emit(tmp_path)
    synthesis = next(t for t in _planner_board(tmp_path) if t.deferred)
    cleared = replace(synthesis, deferred=False, depends_on=())
    plan = wp.plan_wave([cleared], _FANOUT_ORG, [])
    assert [pt.ticket_id for pt in plan.dispatch] == [cleared.ticket_id]


def test_fanout_emission_produces_children_and_a_dependent_synthesis(tmp_path):
    _emit(tmp_path)
    fm = _load_all_fm(tmp_path)
    children = [k for k, v in fm.items() if not v.get("defer")]
    synthesis = [k for k, v in fm.items() if v.get("defer", "").lower() == "true"]
    assert len(children) == len(_THREE_CHILDREN)
    assert len(synthesis) == 1
    depends = _DAS_RE.findall(fm[synthesis[0]].get("depends_on", ""))
    assert sorted(depends) == sorted(children)


def test_planner_keeps_the_dep_blocked_rule_on_a_fanout_board(tmp_path):
    _emit(tmp_path)
    tickets = _planner_board(tmp_path)
    synthesis = next(t for t in tickets if t.deferred)
    assert synthesis.depends_on

    undeferred = [replace(t, deferred=False) for t in tickets]
    plan = wp.plan_wave(undeferred, _FANOUT_ORG, [])
    refusal = next(r for r in plan.refused if r.ticket_id == synthesis.ticket_id)
    assert refusal.reason is wp.RefusalReason.UNMET_DEPENDENCY
    for dep in synthesis.depends_on:
        assert dep in refusal.detail
