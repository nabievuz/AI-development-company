
from __future__ import annotations

import json
from pathlib import Path

OVER_BUDGET_THRESHOLD_PCT = 10.0


def _over_budget(fixtures: Path) -> set[str]:
    data = json.loads((fixtures / "budget.json").read_text(encoding="utf-8"))
    out = set()
    for dept in data.get("departments", []):
        budget = dept.get("budget", 0)
        actual = dept.get("actual", 0)
        if not budget:
            continue
        variance_pct = (actual - budget) / budget * 100.0
        if variance_pct > OVER_BUDGET_THRESHOLD_PCT:
            out.add(str(dept.get("name")))
    return out


def verify(submission: dict, fixtures: Path) -> float:
    expected = _over_budget(fixtures)
    if not expected:
        return 0.0

    reported = submission.get("over_budget", [])
    if not isinstance(reported, list):
        return 0.0
    reported_set = {str(x) for x in reported}

    hits = len(reported_set & expected)
    false_pos = len(reported_set - expected)
    return max(0.0, (hits - false_pos) / len(expected))
