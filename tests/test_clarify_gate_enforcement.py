#!/usr/bin/env python3
"""tests/test_clarify_gate_enforcement.py — ADR-0014 clarify-gate enforcement guarantees.

The clarify gate has two enforcement layers; this pins both so neither silently rots:

1. BACKSTOP (hard, CI-enforced): `check_clarifications --strict` fails on an unresolved
   marker in ANY active status (in_progress / in_review / done). So a marked ticket can
   never reach an active state — and thus can never be merged — even if the orchestrator
   forgets to skip it. This makes the gate's CORRECTNESS enforced, not advisory.

2. ROUTING + CIRCUIT-BREAKER (runtime wave behaviour, not repo state): these are
   /daslab-cycle orchestrator directives — a static CI check can't observe a wave, so
   they are not separately enforceable. We guard them against silent deletion by
   asserting the rule tokens remain present in the skill, and we name the validator that
   backstops them.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import check_clarifications as cc  # noqa: E402  (import after path manipulation)

CYCLE_SKILL = REPO_ROOT / ".claude" / "skills" / "daslab-cycle" / "SKILL.md"


def _board_with(tmp_path: Path, status: str, body: str) -> Path:
    tickets = tmp_path / "tickets"
    tickets.mkdir()
    (tickets / "DAS-4000-t.md").write_text(
        f"---\nid: DAS-4000\nstatus: {status}\nauthor: senior-pm\n---\n\n## Description\n{body}\n",
        encoding="utf-8",
    )
    return tickets


# --------------------------------------------------------------------------- #
# Layer 1 — the hard backstop (correctness, CI-enforced)
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("status", ["in_progress", "in_review", "done"])
def test_backstop_blocks_marker_in_every_active_status(tmp_path, status):
    tickets = _board_with(tmp_path, status, "[NEEDS CLARIFICATION: which provider?]")
    assert cc.main(["--tickets", str(tickets), "--strict"]) == 1


def test_backstop_allows_clean_active_ticket(tmp_path):
    tickets = _board_with(tmp_path, "done", "fully specified, no markers")
    assert cc.main(["--tickets", str(tickets), "--strict"]) == 0


# --------------------------------------------------------------------------- #
# Layer 2 — skill-rule guards (against silent deletion of the runtime directives)
# --------------------------------------------------------------------------- #

def _skill() -> str:
    return CYCLE_SKILL.read_text(encoding="utf-8")


def _skill_flat() -> str:
    """Skill text with whitespace collapsed, so a line-wrapped phrase still matches."""
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
