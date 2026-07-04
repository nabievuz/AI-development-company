#!/usr/bin/env python3
"""tests/test_fanout_deferred.py — Fanout emission + deferred-synthesis gating (DAS-1449).

Verifies:
  1. emit_fanout produces N child tickets + exactly 1 synthesis ticket.
  2. Synthesis ticket has ``defer: true`` and ``depends_on`` = all child ids.
  3. Each child carries its own private payload; synthesis never sees raw sibling payloads.
  4. N is determined at runtime (not hard-coded); different call sites produce N=1, N=5, …
  5. Dispatcher gating: synthesis is dep-blocked while ANY child is not done.
  6. ``defer: true`` hard guard: synthesis refuses even if only one child remains open.
  7. Once ALL children are done, synthesis becomes actionable.
  8. Emitted fanout cluster passes ``scripts/check_dependency_graph.py``.
  9. ``defer: true`` with empty ``depends_on`` fails ``check_dependency_graph``.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import check_dependency_graph as dg  # noqa: E402 (import after path manipulation)
from board_lint import parse_frontmatter  # noqa: E402
from fanout import emit_fanout, is_actionable  # noqa: E402

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

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
    """Convenience wrapper around emit_fanout."""
    return emit_fanout(
        board_dir=board_dir,
        parent_id="DAS-9000",
        parent_meta=_PARENT_META,
        children_payloads=children if children is not None else _THREE_CHILDREN,
        synthesis_meta=synthesis if synthesis is not None else _SYNTHESIS_META,
        date="2026-07-03",
    )


def _load_all_fm(board_dir: Path) -> dict[str, dict[str, str]]:
    """Return {ticket_id: frontmatter_dict} for every DAS-*.md in *board_dir*."""
    result: dict[str, dict[str, str]] = {}
    for md in sorted(board_dir.glob("DAS-*.md")):
        fm = parse_frontmatter(md.read_text(encoding="utf-8"))
        if fm and fm.get("id"):
            result[fm["id"]] = fm
    return result


def _ticket_text(board_dir: Path, ticket_id: str) -> str:
    """Return full text of the ticket file for *ticket_id*."""
    for md in sorted(board_dir.glob("DAS-*.md")):
        text = md.read_text(encoding="utf-8")
        if re.search(rf"^id:\s*{re.escape(ticket_id)}\s*$", text, re.MULTILINE):
            return text
    raise FileNotFoundError(f"No ticket file found for {ticket_id} in {board_dir}")


# ---------------------------------------------------------------------------
# 1. Emission: shape
# ---------------------------------------------------------------------------

def test_emit_produces_n_children_plus_one_synthesis(tmp_path):
    """emit_fanout returns len(children) child ids + exactly one synthesis id."""
    child_ids, synthesis_id = _emit(tmp_path, children=_THREE_CHILDREN[:2])
    assert len(child_ids) == 2
    assert synthesis_id.startswith("DAS-")
    fms = _load_all_fm(tmp_path)
    for cid in child_ids:
        assert cid in fms, f"child ticket {cid} not found on disk"
    assert synthesis_id in fms, "synthesis ticket not found on disk"
    # Total: 2 children + 1 synthesis.
    assert len(list(tmp_path.glob("DAS-*.md"))) == 3


def test_synthesis_has_defer_true(tmp_path):
    """Synthesis frontmatter carries ``defer: true``."""
    _, synthesis_id = _emit(tmp_path)
    fms = _load_all_fm(tmp_path)
    assert fms[synthesis_id].get("defer", "").lower() == "true"


def test_synthesis_depends_on_all_children(tmp_path):
    """Synthesis ``depends_on`` field lists every child id."""
    child_ids, synthesis_id = _emit(tmp_path)
    fms = _load_all_fm(tmp_path)
    dep_raw = fms[synthesis_id].get("depends_on", "")
    dep_ids = set(_DAS_RE.findall(dep_raw))
    assert dep_ids == set(child_ids), (
        f"synthesis depends_on {dep_ids!r} != children {set(child_ids)!r}"
    )


def test_children_have_no_depends_on(tmp_path):
    """Child tickets declare no depends_on (they are immediately actionable)."""
    child_ids, _ = _emit(tmp_path)
    fms = _load_all_fm(tmp_path)
    for cid in child_ids:
        dep_raw = fms[cid].get("depends_on", "")
        assert not dep_raw, f"child {cid} unexpectedly has depends_on: {dep_raw!r}"


def test_children_have_parent_set(tmp_path):
    """Child tickets carry ``parent: DAS-9000``."""
    child_ids, _ = _emit(tmp_path)
    fms = _load_all_fm(tmp_path)
    for cid in child_ids:
        assert fms[cid].get("parent", "") == "DAS-9000"


def test_synthesis_has_parent_set(tmp_path):
    """Synthesis ticket also carries the fanout parent id."""
    _, synthesis_id = _emit(tmp_path)
    fms = _load_all_fm(tmp_path)
    assert fms[synthesis_id].get("parent", "") == "DAS-9000"


# ---------------------------------------------------------------------------
# 2. Private-payload isolation
# ---------------------------------------------------------------------------

def test_private_payloads_isolated_from_siblings(tmp_path):
    """Each child's payload is in its own file; sibling files must not contain it."""
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
        # Owner file must contain its own payload.
        assert payload in id_to_text[owner_id], (
            f"{owner_id} is missing its own payload"
        )
        # All other files (siblings + synthesis) must NOT contain it.
        for other_id, other_text in id_to_text.items():
            if other_id != owner_id:
                assert payload not in other_text, (
                    f"payload of {owner_id!r} leaked into {other_id!r}"
                )


def test_synthesis_body_contains_no_raw_child_payloads(tmp_path):
    """Synthesis ticket body must not contain any child's private payload text."""
    child_ids, synthesis_id = _emit(tmp_path, children=_THREE_CHILDREN)
    synth_text = _ticket_text(tmp_path, synthesis_id)
    for child in _THREE_CHILDREN:
        assert child["payload"] not in synth_text, (
            f"synthesis contains raw child payload: {child['payload']!r}"
        )


# ---------------------------------------------------------------------------
# 3. N is runtime-determined
# ---------------------------------------------------------------------------

def test_n_is_runtime_determined(tmp_path):
    """N = len(children_payloads) — determined at call time, not hard-coded."""
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
    """emit_fanout raises ValueError when children_payloads is empty."""
    with pytest.raises(ValueError, match="non-empty"):
        _emit(tmp_path, children=[])


# ---------------------------------------------------------------------------
# 4 & 5. Dispatcher gating — dep-blocked skip (SKILL.md step 3)
# ---------------------------------------------------------------------------

def test_synthesis_dep_blocked_while_all_children_todo(tmp_path):
    """Synthesis is dep-blocked (not actionable) when all children are todo."""
    child_ids, synthesis_id = _emit(tmp_path, children=_THREE_CHILDREN[:2])
    fms = _load_all_fm(tmp_path)
    assert not is_actionable(fms[synthesis_id], fms), (
        "synthesis must be dep-blocked while children are todo"
    )


def test_synthesis_blocked_when_one_child_remains_open(tmp_path):
    """Synthesis remains dep-blocked even if only ONE child is not yet done."""
    child_ids, synthesis_id = _emit(tmp_path, children=_THREE_CHILDREN)
    fms = _load_all_fm(tmp_path)
    fms[child_ids[0]]["status"] = "done"
    fms[child_ids[1]]["status"] = "done"
    # child_ids[2] remains "todo"
    assert not is_actionable(fms[synthesis_id], fms), (
        "synthesis must be dep-blocked while even one child is not done"
    )


def test_synthesis_actionable_once_all_children_done(tmp_path):
    """Synthesis becomes actionable once ALL children are done."""
    child_ids, synthesis_id = _emit(tmp_path, children=_THREE_CHILDREN[:2])
    fms = _load_all_fm(tmp_path)
    for cid in child_ids:
        fms[cid]["status"] = "done"
    assert is_actionable(fms[synthesis_id], fms), (
        "synthesis must be actionable when all children are done"
    )


def test_children_are_immediately_actionable(tmp_path):
    """Child tickets (no depends_on) are immediately actionable."""
    child_ids, _ = _emit(tmp_path, children=_THREE_CHILDREN[:2])
    fms = _load_all_fm(tmp_path)
    for cid in child_ids:
        assert is_actionable(fms[cid], fms), f"{cid} must be immediately actionable"


# ---------------------------------------------------------------------------
# 6. defer: true hard guard edge cases
# ---------------------------------------------------------------------------

def test_defer_hard_guard_fires_independently():
    """The defer: true hard guard re-checks deps even after the dep-blocked pass."""
    fm_synth = {
        "id": "DAS-9999",
        "status": "todo",
        "defer": "true",
        "depends_on": "[DAS-9998]",
    }
    fm_child_open = {"id": "DAS-9998", "status": "in_progress"}
    fms_by_id = {"DAS-9999": fm_synth, "DAS-9998": fm_child_open}

    # Child not done → synthesis blocked.
    assert not is_actionable(fm_synth, fms_by_id)

    # Mark child done → synthesis actionable.
    fm_child_open["status"] = "done"
    assert is_actionable(fm_synth, fms_by_id)


def test_defer_true_with_no_deps_is_actionable():
    """defer: true with NO depends_on is actionable (nothing to wait on).

    This shape should never be produced by emit_fanout (and is a dep-graph
    violation), but the dispatcher must not hang if it encounters it.
    """
    fm = {"id": "DAS-9999", "status": "todo", "defer": "true", "depends_on": ""}
    assert is_actionable(fm, {"DAS-9999": fm})


def test_is_actionable_respects_non_todo_status():
    """is_actionable returns False for done/blocked/in_review tickets."""
    for bad_status in ("done", "blocked", "in_review", "backlog"):
        fm = {"id": "DAS-1", "status": bad_status}
        assert not is_actionable(fm, {"DAS-1": fm}), (
            f"expected not-actionable for status={bad_status!r}"
        )


# ---------------------------------------------------------------------------
# 7. check_dependency_graph validates emitted cluster
# ---------------------------------------------------------------------------

def test_emitted_fanout_passes_dep_graph(tmp_path):
    """An emitted fanout cluster passes check_dependency_graph (no violations)."""
    _emit(tmp_path)
    assert dg.main(["--board", str(tmp_path)]) == 0


def test_defer_true_with_empty_depends_on_fails_dep_graph(tmp_path):
    """check_dependency_graph rejects defer: true with no depends_on."""
    bad = tmp_path / "DAS-1-bad-deferred.md"
    bad.write_text(
        "---\nid: DAS-1\ntitle: Bad deferred\nstatus: todo\nassignee: qa-eng\n"
        "author: ceo\ndept: engineering\npriority: p1\n"
        "created: 2026-07-03\nupdated: 2026-07-03\ndefer: true\n---\n\n## Log\n",
        encoding="utf-8",
    )
    assert dg.main(["--board", str(tmp_path)]) == 1


def test_real_repo_board_passes_after_extension():
    """The live board still passes check_dependency_graph after this PR's changes."""
    assert dg.main([]) == 0


# ---------------------------------------------------------------------------
# 8. SKILL.md — skill-rule token guards
# ---------------------------------------------------------------------------

def _skill_flat() -> str:
    p = REPO_ROOT / ".claude" / "skills" / "daslab-cycle" / "SKILL.md"
    return " ".join(p.read_text(encoding="utf-8").lower().split())


def test_skill_documents_defer_guard():
    """SKILL.md must mention the defer gating concept."""
    skill = _skill_flat()
    assert "defer" in skill, "SKILL.md must document the defer: true guard"


def test_skill_documents_fanout_emission():
    """SKILL.md step 5 must document fanout emission."""
    skill = _skill_flat()
    assert "fanout" in skill, "SKILL.md must document fanout emission in step 5"


def test_skill_keeps_dep_blocked_rule():
    """The existing dep-blocked rule must still be present in SKILL.md."""
    skill = _skill_flat()
    assert "dep-blocked" in skill
    assert "depends_on" in skill
