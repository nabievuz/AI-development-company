
from __future__ import annotations

import json
from pathlib import Path

DEPTH_THRESHOLD = 3


def _flaggable(fixtures: Path) -> set[str]:
    data = json.loads((fixtures / "components.json").read_text(encoding="utf-8"))
    return {
        str(c.get("name"))
        for c in data.get("components", [])
        if int(c.get("prop_drill_depth", 0)) >= DEPTH_THRESHOLD
        and not c.get("uses_context", False)
    }


def verify(submission: dict, fixtures: Path) -> float:
    expected = _flaggable(fixtures)
    if not expected:
        return 0.0

    reported = submission.get("flagged", [])
    if not isinstance(reported, list):
        return 0.0
    reported_set = {str(x) for x in reported}

    hits = len(reported_set & expected)
    false_pos = len(reported_set - expected)
    return max(0.0, (hits - false_pos) / len(expected))
