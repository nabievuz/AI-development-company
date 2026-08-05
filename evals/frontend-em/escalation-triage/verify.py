
from __future__ import annotations

import json
from pathlib import Path

STUCK_WAVES_THRESHOLD = 1


def _escalate_set(fixtures: Path) -> set[str]:
    data = json.loads((fixtures / "decisions.json").read_text(encoding="utf-8"))
    return {
        str(d.get("id"))
        for d in data.get("decisions", [])
        if d.get("cross_dept_impact", False)
        or d.get("exceeds_charter_authority", False)
        or int(d.get("blocked_waves", 0)) > STUCK_WAVES_THRESHOLD
    }


def verify(submission: dict, fixtures: Path) -> float:
    expected = _escalate_set(fixtures)
    if not expected:
        return 0.0

    reported = submission.get("escalate", [])
    if not isinstance(reported, list):
        return 0.0
    reported_set = {str(x) for x in reported}

    hits = len(reported_set & expected)
    false_pos = len(reported_set - expected)
    return max(0.0, (hits - false_pos) / len(expected))
