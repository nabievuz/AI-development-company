#!/usr/bin/env python3

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import metrics_lib


class TestCompletionIsAboutTheTicketNotTheDispatch:
    def test_a_blocked_ticket_is_not_a_completion(self):
        ev = {"event_type": "run_end", "outcome": "success", "final_status": "blocked"}
        assert metrics_lib._is_completion_event(ev) is False

    def test_a_ticket_still_in_review_is_not_a_completion(self):
        ev = {"event_type": "run_end", "outcome": "success", "final_status": "in_review"}
        assert metrics_lib._is_completion_event(ev) is False

    def test_a_terminal_ticket_is_a_completion(self):
        for status in ("done", "closed", "merged", "shipped"):
            ev = {"event_type": "run_end", "outcome": "success", "final_status": status}
            assert metrics_lib._is_completion_event(ev) is True, status

    def test_an_event_without_final_status_keeps_the_stricter_old_reading(self):
        ev = {"event_type": "run_end", "outcome": "success"}
        assert metrics_lib._is_completion_event(ev) is True

    def test_a_blocked_run_no_longer_counts_as_a_gamed_completion(self):
        events = [
            {"event_type": "run_end", "ticket_id": "DAS-1", "outcome": "success",
             "final_status": "blocked", "merged_pr": False, "ci_status": "unverified",
             "t7_pass": False},
            {"event_type": "run_end", "ticket_id": "DAS-2", "outcome": "success",
             "final_status": "done", "merged_pr": True, "ci_status": "green",
             "t7_pass": False},
        ]
        gaming = metrics_lib.gaming_violations(events)
        assert gaming["completions"] == 1
        assert len(gaming["violations"]) == 1
        assert "DAS-2" in gaming["violations"][0]
        assert "no T7 pass" in gaming["violations"][0]
        assert "no merged PR" not in gaming["violations"][0]
