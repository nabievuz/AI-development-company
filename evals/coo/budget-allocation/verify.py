"""Deterministic verifier — coo / budget-allocation.

Fractional credit rewards true positives and penalises false positives:

    credit = clamp01( (|reported ∩ funded| - |reported \\ funded|) / |funded| )

The funded set is derived by applying the stated greedy, priority-ordered,
full-fund-or-skip allocation rule to the SAME budget request fixture the
agent was given — doing the task correctly reproduces it — so nothing is
leaked: the fixture is the input, and grading it is the graded skill.
Deterministic (no clock/model). An empty submission scores 0.0.
"""

from __future__ import annotations

import json
from pathlib import Path


def _funded(fixtures: Path) -> set[str]:
    data = json.loads((fixtures / "budget_requests.json").read_text(encoding="utf-8"))
    requests = list(data.get("requests", []))
    # Stable sort by priority_score descending; ties keep fixture order.
    ordered = sorted(
        enumerate(requests),
        key=lambda pair: (-pair[1].get("priority_score", 0), pair[0]),
    )
    remaining = data.get("total_budget_usd", 0)
    funded: set[str] = set()
    for _, req in ordered:
        amount = req.get("amount_usd", 0)
        if amount <= remaining:
            funded.add(str(req.get("dept")))
            remaining -= amount
    return funded


def verify(submission: dict, fixtures: Path) -> float:
    """Return fractional credit in [0.0, 1.0] for one submission."""
    expected = _funded(fixtures)
    if not expected:
        return 0.0

    reported = submission.get("funded_depts", [])
    if not isinstance(reported, list):
        return 0.0
    reported_set = {str(x) for x in reported}

    hits = len(reported_set & expected)
    false_pos = len(reported_set - expected)
    return max(0.0, (hits - false_pos) / len(expected))
