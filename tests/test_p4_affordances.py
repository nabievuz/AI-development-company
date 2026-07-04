#!/usr/bin/env python3
"""tests/test_p4_affordances.py — escalation context + approval digest + memory explain (RFC-003 §2)."""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import approval_digest as ad  # noqa: E402  (import after path manipulation)
import escalation_context as ec  # noqa: E402
import memory_lib as ml  # noqa: E402
import yaml  # noqa: E402

REAL_TAXONOMY = yaml.safe_load((REPO_ROOT / "config" / "risk_taxonomy.yaml").read_text())
MEM_CFG = {"recall": {"min_trust": 0.3}, "ttl_days": {"fact": 180, "default": 120}, "health": {"decay_per_bad": 0.05}}
NOW = dt.datetime(2026, 6, 21)


# --------------------------------------------------------------------------- #
# Escalation context
# --------------------------------------------------------------------------- #

def test_escalation_package_assembles_trace_error_memory():
    events = [
        {"event_type": "routing_decision", "ticket_id": "DAS-1", "from_status": "todo",
         "to_status": "in_progress", "reason": "start", "created_at": "2026-06-21T10:00:00Z"},
        {"event_type": "escalation", "ticket_id": "DAS-1", "reason": "stuck",
         "error": "tool timeout", "created_at": "2026-06-21T10:05:00Z"},
    ]
    mems = [{"id": "m1", "content": "relevant fact", "project": "p", "provenance": "verified_pr",
             "trust_score": 1.0, "created_at": "2026-06-20T00:00:00Z", "mem_type": "fact"}]
    pkg = ec.build_package("DAS-1", events, mems, MEM_CFG, NOW)
    assert len(pkg["decision_trace"]) == 1
    assert pkg["escalations"][0]["error"] == "tool timeout"
    assert pkg["recent_memory"][0]["id"] == "m1"
    rendered = ec.render_package(pkg)
    assert "decision trace" in rendered and "tool timeout" in rendered


def test_escalation_empty_is_graceful():
    pkg = ec.build_package("DAS-9", [], [], MEM_CFG, NOW)
    out = ec.render_package(pkg)
    assert "(no transitions recorded yet)" in out and "(no memory store yet)" in out


def test_escalation_cli_real_board_exit_0():
    assert ec.main(["--ticket", "DAS-1381"]) == 0


# --------------------------------------------------------------------------- #
# Approval digest
# --------------------------------------------------------------------------- #

def test_digest_batches_low_risk_and_escalates_qonun5():
    tickets = [
        {"id": "DAS-1", "title": "fix typo", "status": "in_review"},
        {"id": "DAS-2", "title": "rotate keys", "status": "in_review", "labels": ["security"]},
        {"id": "DAS-3", "title": "not pending", "status": "todo"},
    ]
    d = ad.build_digest(tickets, REAL_TAXONOMY)
    assert [e["id"] for e in d["batchable_low_risk"]] == ["DAS-1"]
    assert [e["id"] for e in d["needs_individual_review"]] == ["DAS-2"]


def test_digest_cli_real_board_exit_0():
    assert ad.main([]) == 0


def test_digest_malformed_taxonomy_fails_closed(tmp_path):
    # a malformed taxonomy must error (exit 2), NEVER default to {} and batch everything
    bad = tmp_path / "tax.yaml"
    bad.write_text("{invalid: [unclosed", encoding="utf-8")
    assert ad.main(["--config", str(bad)]) == 2


def test_escalation_survives_malformed_memory_config(tmp_path):
    bad = tmp_path / "mem.yaml"
    bad.write_text("{invalid: [unclosed", encoding="utf-8")
    rc = ec.main(["--ticket", "DAS-1", "--events", str(tmp_path / "e.jsonl"),
                  "--memory-store", str(tmp_path / "m.jsonl"), "--memory-config", str(bad)])
    assert rc == 0


# --------------------------------------------------------------------------- #
# Memory-health explanation
# --------------------------------------------------------------------------- #

def test_explain_quarantine_reasons():
    assert "quarantined" in ml.explain_exclusion({"status": "quarantined"}, NOW, MEM_CFG)
    assert "contradicts" in ml.explain_exclusion({"contradicts": ["m9"]}, NOW, MEM_CFG)
    assert "expired" in ml.explain_exclusion(
        {"created_at": "2020-01-01T00:00:00Z", "mem_type": "fact", "trust_score": 1.0}, NOW, MEM_CFG)
    assert "below minimum" in ml.explain_exclusion(
        {"trust_score": 0.1, "created_at": "2026-06-20T00:00:00Z", "mem_type": "fact"}, NOW, MEM_CFG)


def test_explain_recallable_is_empty():
    good = {"trust_score": 1.0, "created_at": "2026-06-20T00:00:00Z", "mem_type": "fact"}
    assert ml.explain_exclusion(good, NOW, MEM_CFG) == ""
