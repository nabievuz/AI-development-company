#!/usr/bin/env python3
"""tests/test_adaptive_taxonomy.py — Adaptive Risk Taxonomy (R16 / RFC-002).

The load-bearing test is the IMMUTABILITY GUARD: no history can ever produce a
proposal to recalibrate a never-auto-approve category or 'critical'.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import adaptive_taxonomy as at  # noqa: E402  (import after path manipulation)

TAX = {"never_auto_approve": ["new_goal", "security_sensitive", "schema_migration"]}


def _hist(cls, outcome, n):
    return [{"risk_class": cls, "outcome": outcome} for _ in range(n)]


# --------------------------------------------------------------------------- #
# IMMUTABILITY GUARD — the safety-critical property
# --------------------------------------------------------------------------- #

def test_never_recalibrates_critical():
    # overwhelming clean history must NOT propose relaxing critical
    assert at.propose_recalibration(_hist("critical", "clean", 100), TAX) == []


def test_never_recalibrates_never_auto_categories():
    history = _hist("new_goal", "clean", 100) + _hist("security_sensitive", "clean", 100)
    assert at.propose_recalibration(history, TAX) == []


def test_guard_holds_against_casing_and_whitespace():
    for cls in ("Critical", "CRITICAL", " critical ", "New_Goal", "SECURITY_SENSITIVE", "schema_migration "):
        assert at.propose_recalibration(_hist(cls, "clean", 100), TAX) == [], cls
        assert at.propose_recalibration(_hist(cls, "reverted", 100), TAX) == [], cls


def test_guard_holds_with_empty_or_missing_config():
    # never-auto categories are hard-coded, so an empty/missing/null/string config
    # list can NEVER remove their protection
    for tax in ({}, {"never_auto_approve": []}, {"never_auto_approve": None}, {"never_auto_approve": "new_goal"}):
        assert at.propose_recalibration(_hist("new_goal", "clean", 100), tax) == [], tax
        assert at.propose_recalibration(_hist("critical", "clean", 100), tax) == [], tax


def test_null_config_does_not_crash():
    assert at.propose_recalibration(_hist("medium", "clean", 20), {"never_auto_approve": None})


# --------------------------------------------------------------------------- #
# Soft-tier proposals
# --------------------------------------------------------------------------- #

def test_relax_proposed_for_clean_medium():
    p = at.propose_recalibration(_hist("medium", "clean", 20), TAX)
    assert len(p) == 1 and p[0]["action"] == "relax" and p[0]["class"] == "medium"


def test_escalate_proposed_for_reverted_high():
    history = _hist("high", "clean", 15) + _hist("high", "reverted", 5)  # 25% bad
    p = at.propose_recalibration(history, TAX)
    assert p and p[0]["action"] == "escalate"


def test_insufficient_history_no_proposal():
    assert at.propose_recalibration(_hist("medium", "clean", 5), TAX) == []  # < MIN_SAMPLES


def test_low_class_not_relaxed_further():
    assert at.propose_recalibration(_hist("low", "clean", 50), TAX) == []


# --------------------------------------------------------------------------- #
# GATE-6 draft: evidence-gated, never auto-applied
# --------------------------------------------------------------------------- #

def test_gate6_draft_is_evidence_gated():
    draft = at.to_gate6_draft({"class": "medium", "action": "relax", "reason": "x"}, "2026-06-22T00:00:00Z")
    rec = draft["gate_6_record"]
    assert rec["guardrails"]["max_quality_drop"] == 0
    assert rec["rollout"]["mode"] == "shadow"
    assert rec["approval"]["approved_by"] == ""  # unapproved until a human signs
    assert rec["result"]["status"] == "deferred"


def test_cli_inert():
    assert at.main([]) == 0
