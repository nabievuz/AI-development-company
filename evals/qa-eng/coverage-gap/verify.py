
from __future__ import annotations

import json
from pathlib import Path


def _uncovered(fixtures: Path) -> set[str]:
    data = json.loads((fixtures / "coverage.json").read_text(encoding="utf-8"))
    return {
        str(fn.get("name"))
        for fn in data.get("functions", [])
        if not fn.get("covered", False)
    }


def verify(submission: dict, fixtures: Path) -> float:
    expected = _uncovered(fixtures)
    if not expected:
        return 0.0

    reported = submission.get("uncovered", [])
    if not isinstance(reported, list):
        return 0.0
    reported_set = {str(x) for x in reported}

    hits = len(reported_set & expected)
    false_pos = len(reported_set - expected)
    return max(0.0, (hits - false_pos) / len(expected))
