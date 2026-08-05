
from __future__ import annotations

import json
from pathlib import Path


def _blocking(fixtures: Path) -> set[str]:
    data = json.loads((fixtures / "findings.json").read_text(encoding="utf-8"))
    blocking = set()
    for f in data.get("findings", []):
        severity = f.get("severity")
        if severity == "blocker" or (severity == "major" and f.get("category") == "security"):
            blocking.add(str(f.get("id")))
    return blocking


def verify(submission: dict, fixtures: Path) -> float:
    expected = _blocking(fixtures)
    if not expected:
        return 0.0

    reported = submission.get("blocking", [])
    if not isinstance(reported, list):
        return 0.0
    reported_set = {str(x) for x in reported}

    hits = len(reported_set & expected)
    false_pos = len(reported_set - expected)
    return max(0.0, (hits - false_pos) / len(expected))
