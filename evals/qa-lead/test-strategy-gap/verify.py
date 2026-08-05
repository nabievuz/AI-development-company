
from __future__ import annotations

import json
from pathlib import Path

REQUIRED_BY_RISK = {
    "low": {"unit"},
    "medium": {"unit", "integration"},
    "high": {"unit", "integration", "e2e", "security"},
}


def _missing(fixtures: Path) -> set[str]:
    data = json.loads((fixtures / "feature.json").read_text(encoding="utf-8"))
    required = REQUIRED_BY_RISK.get(data.get("risk_level"), set())
    existing = {str(t) for t in data.get("existing_test_plan", [])}
    return required - existing


def verify(submission: dict, fixtures: Path) -> float:
    expected = _missing(fixtures)
    if not expected:
        return 0.0

    reported = submission.get("missing_test_types", [])
    if not isinstance(reported, list):
        return 0.0
    reported_set = {str(x) for x in reported}

    hits = len(reported_set & expected)
    false_pos = len(reported_set - expected)
    return max(0.0, (hits - false_pos) / len(expected))
