#!/usr/bin/env python3
"""tests/test_gen_subagents_effort.py — ADR-0013 effort-tier mapping (ADR-0002 coverage).

Locks the per-role effort bands that `gen_subagents.load_alloc()` derives from the
4-column `governance/policies/model-allocation.md` table, so a future edit that drops
the effort cell (falling back to defaults) or re-bands a role is caught here in
addition to the `gen_subagents && git diff` drift gate.
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import gen_subagents as gs  # noqa: E402  (import after path manipulation)

OPUS_HIGH = {
    "cto", "security-lead", "ceo", "chairman", "cpo", "senior-pm",
    "backend-em", "frontend-em", "qa-lead", "sre-lead",
}
SONNET_MEDIUM = {
    "backend-eng-1", "backend-eng-2", "frontend-eng-1", "frontend-eng-2",
    "qa-eng", "security-eng", "sre-eng", "design-lead", "product-designer",
    "ux-researcher", "product-analyst", "legal-analyst", "finance-analyst",
}
SONNET_LOW = {"content-lead", "growth-marketer", "cdo", "cmo", "coo", "board-member"}
HAIKU_NONE = {"seo-specialist", "support-lead", "tech-writer"}


def test_table_parses_to_exactly_the_32_roles():
    models, _ = gs.load_alloc()
    assert set(models) == OPUS_HIGH | SONNET_MEDIUM | SONNET_LOW | HAIKU_NONE


def test_model_tier_counts():
    models, _ = gs.load_alloc()
    assert Counter(models.values()) == {"opus": 10, "sonnet": 19, "haiku": 3}


def test_opus_roles_effort_high():
    _, efforts = gs.load_alloc()
    for role in OPUS_HIGH:
        assert efforts[role] == "high", role


def test_sonnet_medium_band():
    _, efforts = gs.load_alloc()
    for role in SONNET_MEDIUM:
        assert efforts[role] == "medium", role


def test_sonnet_low_band():
    _, efforts = gs.load_alloc()
    for role in SONNET_LOW:
        assert efforts[role] == "low", role


def test_haiku_takes_no_effort():
    _, efforts = gs.load_alloc()
    for role in HAIKU_NONE:
        assert efforts[role] is None, role


def test_no_role_runs_at_max_effort():
    # ADR-0013 retired uniform `max`; nothing should regress to it.
    _, efforts = gs.load_alloc()
    assert "max" not in set(efforts.values())
