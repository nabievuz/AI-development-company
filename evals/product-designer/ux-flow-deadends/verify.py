
from __future__ import annotations

import json
from pathlib import Path


def _dead_ends(fixtures: Path) -> set[str]:
    data = json.loads((fixtures / "flow.json").read_text(encoding="utf-8"))
    return {
        str(screen.get("name"))
        for screen in data.get("screens", [])
        if not screen.get("transitions") and not screen.get("terminal", False)
    }


def verify(submission: dict, fixtures: Path) -> float:
    expected = _dead_ends(fixtures)
    if not expected:
        return 0.0

    reported = submission.get("dead_ends", [])
    if not isinstance(reported, list):
        return 0.0
    reported_set = {str(x) for x in reported}

    hits = len(reported_set & expected)
    false_pos = len(reported_set - expected)
    return max(0.0, (hits - false_pos) / len(expected))
