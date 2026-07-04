"""Deterministic verifier — support-lead / sla-breach-check.

No wall-clock or randomness: the reference "now" is a fixed value read from
fixtures/policy.json, so the same submission always scores the same.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def _breached(now: datetime, limit_hours: float, created_at: str, first_response_at: str | None) -> bool:
    end = _parse(first_response_at) if first_response_at else now
    elapsed_hours = (end - _parse(created_at)).total_seconds() / 3600.0
    return elapsed_hours > limit_hours


def verify(submission: dict, fixtures: Path) -> float:
    policy = json.loads((fixtures / "policy.json").read_text(encoding="utf-8"))
    tickets = json.loads((fixtures / "tickets.json").read_text(encoding="utf-8"))["tickets"]
    now = _parse(policy["now"])
    limits = policy["first_response_hours"]

    breaches = submission.get("breaches")
    if not isinstance(breaches, dict) or not tickets:
        return 0.0

    correct = 0
    for ticket in tickets:
        tid = ticket["id"]
        expected = _breached(
            now, limits[ticket["priority"]], ticket["created_at"], ticket["first_response_at"]
        )
        actual = breaches.get(tid)
        if isinstance(actual, bool) and actual == expected:
            correct += 1
    return correct / len(tickets)
