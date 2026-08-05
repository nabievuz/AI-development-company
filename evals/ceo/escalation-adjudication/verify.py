
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
