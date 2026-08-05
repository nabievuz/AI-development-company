from __future__ import annotations

import json
from pathlib import Path


_ANSWERS = {
    "T-101": {"category": "billing", "route": "billing-team", "priority": "P2"},
    "T-102": {"category": "bug", "route": "eng-oncall", "priority": "P1"},
    "T-103": {"category": "how-to", "route": "support-tier2", "priority": "P3"},
    "T-104": {"category": "feature-request", "route": "product", "priority": "P3"},
    "T-105": {"category": "account-access", "route": "support-tier2", "priority": "P1"},
}

_FIELDS = ("category", "route", "priority")


def verify(submission: dict, fixtures: Path) -> float:
    tickets = json.loads((fixtures / "tickets.json").read_text(encoding="utf-8"))["tickets"]
    triage = submission.get("triage")
    if not isinstance(triage, dict) or not tickets:
        return 0.0

    total_fields = len(tickets) * len(_FIELDS)
    correct = 0
    for ticket in tickets:
        tid = ticket["id"]
        answer = _ANSWERS[tid]
        entry = triage.get(tid)
        if not isinstance(entry, dict):
            continue
        for field in _FIELDS:
            if entry.get(field) == answer[field]:
                correct += 1
    return correct / total_fields
