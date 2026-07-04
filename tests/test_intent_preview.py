#!/usr/bin/env python3
"""tests/test_intent_preview.py — Agent Intent Preview (R10 / RFC-003 §2)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import intent_preview as ip  # noqa: E402  (import after path manipulation)
import yaml  # noqa: E402

REAL_TAXONOMY = yaml.safe_load((REPO_ROOT / "config" / "risk_taxonomy.yaml").read_text())
REAL_CONFIG = REPO_ROOT / "config" / "risk_taxonomy.yaml"


def test_auto_approvable_plan():
    plan = {"ticket_id": "DAS-1", "role": "backend-eng-1", "model": "sonnet",
            "summary": "refactor a helper", "ticket_type": "feature"}
    intent = ip.build_intent(plan, REAL_TAXONOMY)
    assert intent["needs_human_approval"] is False
    assert "auto-approvable" in ip.render_intent(intent)


def test_new_goal_plan_needs_human():
    plan = {"ticket_id": "DAS-2", "role": "ceo", "model": "opus",
            "summary": "start a new product", "ticket_type": "goal"}
    intent = ip.build_intent(plan, REAL_TAXONOMY)
    assert intent["needs_human_approval"] is True
    assert "new_goal" in intent["never_auto_approve_categories"]
    assert "REQUIRES HUMAN APPROVAL" in ip.render_intent(intent)


def test_security_path_plan_needs_human():
    plan = {"ticket_id": "DAS-3", "role": "security-eng", "model": "opus",
            "summary": "touch auth", "paths": ["src/auth/login.py"]}
    assert ip.build_intent(plan, REAL_TAXONOMY)["needs_human_approval"] is True


def test_tools_rendered():
    plan = {"ticket_id": "DAS-4", "role": "x", "model": "haiku",
            "summary": "fmt", "planned_tools": ["read", "edit"]}
    assert "read, edit" in ip.render_intent(ip.build_intent(plan, REAL_TAXONOMY))


def test_cli_plan_file(tmp_path):
    p = tmp_path / "plan.json"
    p.write_text(json.dumps({"ticket_id": "DAS-9", "role": "r", "model": "sonnet",
                             "summary": "s", "ticket_type": "goal"}), encoding="utf-8")
    assert ip.main(["--plan-file", str(p), "--config", str(REAL_CONFIG)]) == 0


def test_cli_missing_inputs_exit_2(tmp_path):
    assert ip.main(["--config", str(REAL_CONFIG)]) == 2


def test_cli_ticket_from_real_board(tmp_path):
    # An existing board ticket renders an intent preview (exit 0). The live
    # platform board may be empty (platform-only; project tickets live in
    # projects/<slug>/board-tickets/), so fall back to a real archived ticket.
    live_tickets = sorted((REPO_ROOT / "board" / "tickets").glob("DAS-*.md"))
    if live_tickets:
        ticket_id = "-".join(live_tickets[0].name.split("-", 2)[:2])
        assert ip.main(["--ticket", ticket_id]) == 0
        return
    archived = sorted((REPO_ROOT / "board" / "archive").glob("*/DAS-*.md"))
    if not archived:
        import pytest

        pytest.skip("no live or archived tickets to exercise intent_preview against")
    src = archived[0]
    board = tmp_path / "board"
    (board / "tickets").mkdir(parents=True)
    (board / "tickets" / src.name).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    ticket_id = "-".join(src.name.split("-", 2)[:2])
    assert ip.main(["--ticket", ticket_id, "--board", str(board)]) == 0


def test_malformed_ticket_is_fail_closed(tmp_path):
    # a ticket with unparseable frontmatter must NOT preview as auto-approvable
    board = tmp_path / "board"
    (board / "tickets").mkdir(parents=True)
    (board / "tickets" / "DAS-9.md").write_text(
        "---\napproval: auto\nticket_type: goal\nfoo: [unclosed\n---\nbody\n", encoding="utf-8")
    intent = ip.build_intent(ip.ticket_plan(board, "DAS-9"), REAL_TAXONOMY)
    assert intent["needs_human_approval"] is True
    assert "unparseable" in " ".join(intent["never_auto_approve_categories"])


def test_cli_malformed_plan_json_exit_2(tmp_path):
    p = tmp_path / "plan.json"
    p.write_text("{bad json", encoding="utf-8")
    assert ip.main(["--plan-file", str(p), "--config", str(REAL_CONFIG)]) == 2


def test_cli_non_dict_plan_exit_2(tmp_path):
    p = tmp_path / "plan.json"
    p.write_text("[1, 2, 3]", encoding="utf-8")
    assert ip.main(["--plan-file", str(p), "--config", str(REAL_CONFIG)]) == 2
