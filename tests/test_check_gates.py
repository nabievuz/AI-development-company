"""tests/test_check_gates.py — pytest suite for scripts/check_gates.py.

Each test builds a synthetic ticket board (a list of frontmatter dicts) and
asserts that ``check_gates`` fires exactly when the AADL gate order is
violated, and stays silent when gate order is respected.

Rules under test
----------------
G1  Ticket at stage N actionable while GATE-(N-1) not done  → violation fires
G2  Ticket at stage N actionable with GATE-(N-1) done       → no violation
G3  Ticket at stage 1 is always allowed (no prior gate)     → no violation
G4  Ticket without a parent is not checked                  → no violation
G5  Multiple goals are checked independently                → isolation holds
G6  Deeper nesting (grandchild) resolves stage via ancestor → violation fires
G7  Prior gate missing entirely (no record) → no false positive → no violation
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make scripts/ importable regardless of how pytest is invoked.
_REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

from check_gates import (  # noqa: E402
    build_gate_map,
    check_gates,
    extract_stage_number,
    is_gate_epic,
    load_tickets,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BASE_GATE_EPIC: dict[str, str] = {
    "id": "DAS-9000",
    "title": "Project X — Stage 1: Planning (GATE-1)",
    "status": "done",
    "assignee": "cpo",
    "author": "ceo",
    "dept": "product",
    "priority": "p0",
    "parent": "",
    "goal": "proj-x",
    "created": "2026-06-18",
    "updated": "2026-06-18",
}

_BASE_CHILD: dict[str, str] = {
    "id": "DAS-9001",
    "title": "Child task",
    "status": "todo",
    "assignee": "qa-eng",
    "author": "ceo",
    "dept": "engineering",
    "priority": "p1",
    "parent": "DAS-9000",
    "goal": "proj-x",
    "created": "2026-06-18",
    "updated": "2026-06-18",
}


def gate_epic(stage: int, status: str, goal: str = "proj-x", ticket_id: str = "") -> dict[str, str]:
    """Return a gate-epic frontmatter dict for the given stage and status."""
    tid = ticket_id or f"DAS-{9000 + stage}"
    return {
        "id": tid,
        "title": f"Project — Stage {stage}: Gate close (GATE-{stage})",
        "status": status,
        "assignee": "cpo",
        "author": "ceo",
        "dept": "engineering",
        "priority": "p0",
        "parent": "",
        "goal": goal,
        "created": "2026-06-18",
        "updated": "2026-06-18",
    }


def child_ticket(
    ticket_id: str,
    parent_id: str,
    status: str = "todo",
    goal: str = "proj-x",
) -> dict[str, str]:
    """Return a child-ticket frontmatter dict."""
    return {
        "id": ticket_id,
        "title": f"Child {ticket_id}",
        "status": status,
        "assignee": "qa-eng",
        "author": "ceo",
        "dept": "engineering",
        "priority": "p1",
        "parent": parent_id,
        "goal": goal,
        "created": "2026-06-18",
        "updated": "2026-06-18",
    }


def run_check(tickets_fm: list[dict[str, str]]) -> list[str]:
    """Wrap frontmatter dicts in (Path, fm) pairs and call check_gates."""
    fake_path = Path("board/tickets/DAS-FAKE.md")
    pairs = [(fake_path, fm) for fm in tickets_fm]
    return check_gates(pairs)


# ---------------------------------------------------------------------------
# Unit tests: extract_stage_number
# ---------------------------------------------------------------------------


def test_extract_stage_number_valid() -> None:
    assert extract_stage_number("Project — Stage 3: Dev build (GATE-3)") == 3


def test_extract_stage_number_mismatch_returns_none() -> None:
    """Stage 2 in title but GATE-3 → mismatch → None."""
    assert extract_stage_number("Project — Stage 2: Dev (GATE-3)") is None


def test_extract_stage_number_no_stage_returns_none() -> None:
    assert extract_stage_number("Some random ticket title") is None


def test_extract_stage_number_all_stages() -> None:
    for n in range(1, 7):
        title = f"Proj — Stage {n}: Close (GATE-{n})"
        assert extract_stage_number(title) == n


# ---------------------------------------------------------------------------
# Unit tests: is_gate_epic
# ---------------------------------------------------------------------------


def test_is_gate_epic_true() -> None:
    fm = gate_epic(stage=2, status="done")
    assert is_gate_epic(fm) is True


def test_is_gate_epic_false_has_parent() -> None:
    fm = gate_epic(stage=2, status="done")
    fm["parent"] = "DAS-8000"
    assert is_gate_epic(fm) is False


def test_is_gate_epic_false_no_stage_in_title() -> None:
    fm = dict(_BASE_CHILD)
    fm["parent"] = ""
    assert is_gate_epic(fm) is False


# ---------------------------------------------------------------------------
# G1 — Violation fires when prior gate is NOT done
# ---------------------------------------------------------------------------


def test_violation_fires_prior_gate_not_done() -> None:
    """GATE-1 is open (todo); a Stage-2 child is actionable → violation."""
    gate1 = gate_epic(stage=1, status="todo", ticket_id="DAS-1001")
    gate2 = gate_epic(stage=2, status="in_progress", ticket_id="DAS-1002")
    child = child_ticket("DAS-1003", parent_id="DAS-1002", status="todo")

    violations = run_check([gate1, gate2, child])
    assert len(violations) >= 1
    assert any("DAS-1003" in v for v in violations), violations
    assert any("GATE-1" in v for v in violations), violations
    assert any("stage 2" in v for v in violations), violations


def test_violation_fires_prior_gate_in_progress() -> None:
    """Prior gate in_progress counts as not-done → violation fires."""
    gate2 = gate_epic(stage=2, status="in_progress", ticket_id="DAS-1002")
    gate3 = gate_epic(stage=3, status="in_progress", ticket_id="DAS-1003")
    child = child_ticket("DAS-1004", parent_id="DAS-1003", status="in_progress")

    violations = run_check([gate2, gate3, child])
    assert len(violations) >= 1
    assert any("DAS-1004" in v for v in violations), violations
    assert any("GATE-2" in v for v in violations), violations


def test_violation_fires_for_todo_and_in_progress_statuses() -> None:
    """Both 'todo' and 'in_progress' are considered actionable."""
    gate1_open = gate_epic(stage=1, status="in_progress", ticket_id="DAS-1001")
    gate2_open = gate_epic(stage=2, status="todo", ticket_id="DAS-1002")
    child_todo = child_ticket("DAS-1003", parent_id="DAS-1002", status="todo")
    child_ip = child_ticket("DAS-1004", parent_id="DAS-1002", status="in_progress")

    violations = run_check([gate1_open, gate2_open, child_todo, child_ip])
    ids_flagged = [v.split(":")[0] for v in violations]
    assert "DAS-1003" in ids_flagged, violations
    assert "DAS-1004" in ids_flagged, violations


# ---------------------------------------------------------------------------
# G2 — No violation when prior gate IS done
# ---------------------------------------------------------------------------


def test_no_violation_when_prior_gate_done() -> None:
    """GATE-1 done; Stage-2 child actionable → no violation."""
    gate1 = gate_epic(stage=1, status="done", ticket_id="DAS-1001")
    gate2 = gate_epic(stage=2, status="in_progress", ticket_id="DAS-1002")
    child = child_ticket("DAS-1003", parent_id="DAS-1002", status="todo")

    violations = run_check([gate1, gate2, child])
    assert violations == [], violations


def test_no_violation_all_prior_gates_done() -> None:
    """All prior gates done; stage-5 child actionable → no violation."""
    gates = [gate_epic(stage=n, status="done", ticket_id=f"DAS-100{n}") for n in range(1, 5)]
    gate5 = gate_epic(stage=5, status="in_progress", ticket_id="DAS-1005")
    child = child_ticket("DAS-1006", parent_id="DAS-1005", status="todo")

    violations = run_check(gates + [gate5, child])
    assert violations == [], violations


# ---------------------------------------------------------------------------
# G3 — Stage-1 children are never blocked (no prior gate)
# ---------------------------------------------------------------------------


def test_stage_1_child_never_blocked() -> None:
    """Even if there were a GATE-0, Stage-1 children have no prior gate."""
    gate1 = gate_epic(stage=1, status="todo", ticket_id="DAS-1001")
    child = child_ticket("DAS-1002", parent_id="DAS-1001", status="todo")

    violations = run_check([gate1, child])
    # stage 1 has no prior gate — child must not be flagged
    assert violations == [], violations


# ---------------------------------------------------------------------------
# G4 — Top-level tickets (no parent) are not checked
# ---------------------------------------------------------------------------


def test_top_level_ticket_not_checked() -> None:
    """A gate epic with status 'todo' and no parent must not fire a violation."""
    gate1_open = gate_epic(stage=1, status="todo", ticket_id="DAS-1001")
    # Intentionally no child — only the gate epic itself
    violations = run_check([gate1_open])
    assert violations == [], violations


# ---------------------------------------------------------------------------
# G5 — Multiple goals are checked independently
# ---------------------------------------------------------------------------


def test_multiple_goals_isolated() -> None:
    """Violation in goal-A must not bleed into goal-B."""
    # goal-a: GATE-1 open
    a_gate1 = gate_epic(stage=1, status="todo", goal="goal-a", ticket_id="DAS-1001")
    a_gate2 = gate_epic(stage=2, status="in_progress", goal="goal-a", ticket_id="DAS-1002")
    a_child = child_ticket("DAS-1003", parent_id="DAS-1002", status="todo", goal="goal-a")

    # goal-b: GATE-1 done — no violation expected
    b_gate1 = gate_epic(stage=1, status="done", goal="goal-b", ticket_id="DAS-2001")
    b_gate2 = gate_epic(stage=2, status="in_progress", goal="goal-b", ticket_id="DAS-2002")
    b_child = child_ticket("DAS-2003", parent_id="DAS-2002", status="todo", goal="goal-b")

    violations = run_check([a_gate1, a_gate2, a_child, b_gate1, b_gate2, b_child])

    flagged_ids = [v.split(":")[0] for v in violations]
    assert "DAS-1003" in flagged_ids, violations  # goal-a child should be flagged
    assert "DAS-2003" not in flagged_ids, violations  # goal-b child must NOT be flagged


# ---------------------------------------------------------------------------
# G6 — Grandchild (deeper nesting) resolves stage via ancestor
# ---------------------------------------------------------------------------


def test_grandchild_resolves_stage_via_ancestor() -> None:
    """A grandchild (child of child-of-gate-epic) still resolves to the gate stage."""
    gate1 = gate_epic(stage=1, status="todo", ticket_id="DAS-1001")
    gate2 = gate_epic(stage=2, status="in_progress", ticket_id="DAS-1002")
    # Direct child of gate2
    mid_child = child_ticket("DAS-1003", parent_id="DAS-1002", status="done")
    # Grandchild — parent is mid_child which is not a gate epic
    grandchild = child_ticket("DAS-1004", parent_id="DAS-1003", status="todo")

    violations = run_check([gate1, gate2, mid_child, grandchild])
    flagged_ids = [v.split(":")[0] for v in violations]
    # Grandchild should be flagged because its ancestor is stage 2 and GATE-1 is open
    assert "DAS-1004" in flagged_ids, violations


# ---------------------------------------------------------------------------
# G7 — No prior gate record → no false positive
# ---------------------------------------------------------------------------


def test_no_prior_gate_record_no_false_positive() -> None:
    """If there is no gate epic at all for a goal, no violation should fire."""
    # Ticket has a parent but the parent is not a gate epic and there are no gate epics
    parent_ticket = {
        "id": "DAS-9000",
        "title": "Some non-gate parent",
        "status": "done",
        "assignee": "qa-eng",
        "author": "ceo",
        "dept": "engineering",
        "priority": "p1",
        "parent": "",
        "goal": "no-gates-goal",
        "created": "2026-06-18",
        "updated": "2026-06-18",
    }
    child = child_ticket("DAS-9001", parent_id="DAS-9000", status="todo", goal="no-gates-goal")

    violations = run_check([parent_ticket, child])
    assert violations == [], violations


# ---------------------------------------------------------------------------
# Integration — file-system round-trip via load_tickets
# ---------------------------------------------------------------------------


def make_ticket_file(tmp_path: Path, fm: dict[str, str]) -> Path:
    """Write a frontmatter dict to a DAS-*.md file under *tmp_path*."""
    ticket_id = fm["id"]
    path = tmp_path / f"{ticket_id}-fixture.md"
    lines = ["---"]
    for k, v in fm.items():
        lines.append(f"{k}: {v}")
    lines += ["---", "", "## Description", "Fixture.", "", "## Log"]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_load_tickets_and_check_gates_clean(tmp_path: Path) -> None:
    """Round-trip: write ordered board to disk, load, check — no violations."""
    gate1 = gate_epic(stage=1, status="done", ticket_id="DAS-9001")
    gate2 = gate_epic(stage=2, status="in_progress", ticket_id="DAS-9002")
    child = child_ticket("DAS-9003", parent_id="DAS-9002", status="todo")

    for fm in [gate1, gate2, child]:
        make_ticket_file(tmp_path, fm)

    tickets = load_tickets(tmp_path)
    violations = check_gates(tickets)
    assert violations == [], violations


def test_load_tickets_and_check_gates_violation(tmp_path: Path) -> None:
    """Round-trip: write out-of-order board to disk, load, check — violation fires."""
    gate1 = gate_epic(stage=1, status="todo", ticket_id="DAS-9001")  # GATE-1 open!
    gate2 = gate_epic(stage=2, status="in_progress", ticket_id="DAS-9002")
    child = child_ticket("DAS-9003", parent_id="DAS-9002", status="todo")

    for fm in [gate1, gate2, child]:
        make_ticket_file(tmp_path, fm)

    tickets = load_tickets(tmp_path)
    violations = check_gates(tickets)
    assert len(violations) >= 1, "Expected at least one violation"
    assert any("DAS-9003" in v for v in violations), violations
    assert any("GATE-1" in v for v in violations), violations


def test_build_gate_map_extracts_all_stages(tmp_path: Path) -> None:
    """build_gate_map should collect one entry per stage for each goal."""
    gates = [gate_epic(stage=n, status="done", ticket_id=f"DAS-{9000 + n}") for n in range(1, 5)]
    fake_path = Path("board/tickets/DAS-FAKE.md")
    pairs = [(fake_path, fm) for fm in gates]

    gate_map = build_gate_map(pairs)
    assert "proj-x" in gate_map
    for n in range(1, 5):
        assert gate_map["proj-x"][n] == "done", gate_map
