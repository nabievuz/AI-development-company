"""Deterministic verifier — ceo / escalation-adjudication.

Fractional credit is classification accuracy over the fixture's escalation
records:

    credit = (# ids classified correctly) / (total # ids)

The correct label per id is derived from the SAME fixture the agent was
given, by re-applying the escalation rule stated in task.md — so nothing is
leaked into fixtures/: the fixture is the input, and applying the rule
correctly is the graded skill. Deterministic (no clock/model). An empty
submission scores 0.0.
"""

from __future__ import annotations

import json
from pathlib import Path


def _expected(fixtures: Path) -> dict[str, str]:
    data = json.loads((fixtures / "escalations.json").read_text(encoding="utf-8"))
    labels: dict[str, str] = {}
    for rec in data.get("escalations", []):
        rec_id = str(rec.get("id"))
        over_budget = float(rec.get("budget_usd", 0)) > float(rec.get("charter_limit_usd", 0))
        irreversible_cross_dept = bool(rec.get("cross_dept", False)) and not bool(
            rec.get("reversible", True)
        )
        labels[rec_id] = "escalate" if (over_budget or irreversible_cross_dept) else "decide"
    return labels


def verify(submission: dict, fixtures: Path) -> float:
    """Return fractional credit in [0.0, 1.0] for one submission."""
    expected = _expected(fixtures)
    if not expected:
        return 0.0

    reported = submission.get("decisions", {})
    if not isinstance(reported, dict):
        return 0.0

    correct = 0
    for rec_id, label in expected.items():
        got = reported.get(rec_id)
        if isinstance(got, str) and got.strip().lower() == label:
            correct += 1

    return max(0.0, correct / len(expected))
