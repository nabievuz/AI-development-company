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
import wave_planner as wp
import wave_runner as wr


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


def _clarify_ticket(marker_count: int = 1) -> wp.Ticket:
    body = "## Description\n" + "\n".join(
        f"[NEEDS CLARIFICATION: question {i}?]" for i in range(marker_count)
    )
    return wp.ticket_from_frontmatter(
        {
            "id": "DAS-4000",
            "assignee": "backend-eng-1",
            "status": "todo",
            "author": "senior-pm",
            "zone": "z1",
        },
        fallback_id="DAS-4000",
        body=body,
    )


_ORG = wp.OrgModel(role_models={"backend-eng-1": "sonnet"})


def test_planner_marks_a_clarify_blocked_ticket_non_actionable():
    plan = wp.plan_wave([_clarify_ticket()], _ORG, [])
    assert plan.dispatch == ()
    assert [r.reason for r in plan.refused] == [wp.RefusalReason.CLARIFY_BLOCKED]


def test_planner_routes_a_clarify_blocked_ticket_away_from_a_code_agent():
    ticket = _clarify_ticket()
    plan = wp.plan_wave([ticket], _ORG, [])
    assert ticket.ticket_id not in {pt.ticket_id for pt in plan.dispatch}
    detail = plan.refused[0].detail
    assert "senior-pm" in detail
    assert "never to a code agent" in detail


def test_planner_dispatches_the_same_ticket_once_the_markers_are_resolved():
    resolved = wp.ticket_from_frontmatter(
        {
            "id": "DAS-4000",
            "assignee": "backend-eng-1",
            "status": "todo",
            "author": "senior-pm",
            "zone": "z1",
        },
        fallback_id="DAS-4000",
        body="## Description\nfully specified, no markers",
    )
    plan = wp.plan_wave([resolved], _ORG, [])
    assert [pt.ticket_id for pt in plan.dispatch] == ["DAS-4000"]


def test_planner_uses_the_enforcing_validators_own_marker_pattern():
    assert wp.CLARIFICATION_MARKER_RE is cc.MARKER_RE


def test_clarification_markers_inside_a_code_fence_do_not_block():
    ticket = wp.ticket_from_frontmatter(
        {"id": "DAS-4001", "assignee": "backend-eng-1", "status": "todo", "zone": "z2"},
        fallback_id="DAS-4001",
        body="## Description\n```\n[NEEDS CLARIFICATION: sample only]\n```\n",
    )
    assert ticket.clarification_markers == 0
    assert [pt.ticket_id for pt in wp.plan_wave([ticket], _ORG, []).dispatch] == ["DAS-4001"]


def test_circuit_breaker_trips_when_a_wave_repeats_its_unfinished_set():
    unfinished = [
        wr.TicketResult(
            ticket_id="DAS-4000", outcome="failed", merged_pr=False, ci_status="red",
            t7_pass=False, t7_score=0.0, start="2026-07-04T10:00:00Z",
            end="2026-07-04T10:05:00Z", final_status="in_progress", output="stuck",
        )
    ]
    first = wr.WaveResults.from_ticket_results(unfinished)
    assert first.in_loop is False
    assert first.next_tickets == ["DAS-4000"]

    second = wr.WaveResults.from_ticket_results(
        unfinished, prior_next_tickets=first.next_tickets
    )
    assert second.in_loop is True
    assert second.progress_being_made is False


def test_circuit_breaker_stays_open_when_the_wave_made_progress():
    done = wr.TicketResult(
        ticket_id="DAS-4000", outcome="success", merged_pr=True, ci_status="green",
        t7_pass=True, t7_score=0.9, start="2026-07-04T10:00:00Z",
        end="2026-07-04T10:05:00Z", final_status="done", output="done",
    )
    results = wr.WaveResults.from_ticket_results([done], prior_next_tickets=["DAS-4000"])
    assert results.in_loop is False
    assert results.progress_being_made is True
