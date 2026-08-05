#!/usr/bin/env python3

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import check_clarifications as cc

CYCLE_SKILL = REPO_ROOT / ".claude" / "skills" / "daslab-cycle" / "SKILL.md"


def _board_with(tmp_path: Path, status: str, body: str) -> Path:
    tickets = tmp_path / "tickets"
    tickets.mkdir()
    (tickets / "DAS-4000-t.md").write_text(
        f"---\nid: DAS-4000\nstatus: {status}\nauthor: senior-pm\n---\n\n## Description\n{body}\n",
        encoding="utf-8",
    )
    return tickets


@pytest.mark.parametrize("status", ["in_progress", "in_review", "done"])
def test_backstop_blocks_marker_in_every_active_status(tmp_path, status):
    tickets = _board_with(tmp_path, status, "[NEEDS CLARIFICATION: which provider?]")
    assert cc.main(["--tickets", str(tickets), "--strict"]) == 1


def test_backstop_allows_clean_active_ticket(tmp_path):
    tickets = _board_with(tmp_path, "done", "fully specified, no markers")
    assert cc.main(["--tickets", str(tickets), "--strict"]) == 0


def _skill() -> str:
    return CYCLE_SKILL.read_text(encoding="utf-8")


def _skill_flat() -> str:
    return " ".join(CYCLE_SKILL.read_text(encoding="utf-8").lower().split())


def test_skill_marks_clarify_blocked_non_actionable():
    skill = _skill()
    assert "[NEEDS CLARIFICATION" in skill
    assert "clarify-blocked" in skill


def test_skill_routes_blocked_away_from_code_subagent():
    skill = _skill_flat()
    assert "code subagent" in skill and "reviewer" in skill


def test_skill_keeps_the_circuit_breaker():
    assert "circuit-breaker" in _skill_flat()


def test_skill_names_the_enforcing_validator():
    assert "check_clarifications" in _skill()
