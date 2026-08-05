
from __future__ import annotations

import json
from pathlib import Path

BUNDLE_THRESHOLD_KB = 150


def _splittable(fixtures: Path) -> set[str]:
    data = json.loads((fixtures / "routes.json").read_text(encoding="utf-8"))
    return {
        str(r.get("name"))
        for r in data.get("routes", [])
        if int(r.get("initial_bundle_kb", 0)) > BUNDLE_THRESHOLD_KB
        and not r.get("is_critical_path", False)
    }


def verify(submission: dict, fixtures: Path) -> float:
    expected = _splittable(fixtures)
    if not expected:
        return 0.0

    reported = submission.get("code_split", [])
    if not isinstance(reported, list):
        return 0.0
    reported_set = {str(x) for x in reported}

    hits = len(reported_set & expected)
    false_pos = len(reported_set - expected)
    return max(0.0, (hits - false_pos) / len(expected))
