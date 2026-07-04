"""Deterministic verifier — qa-lead / test-strategy-gap.

Fractional credit rewards true positives and penalises false positives:

    credit = clamp01( (|reported ∩ missing| - |reported \\ missing|) / |missing| )

Required-coverage-by-risk policy (derived from the SAME fixture the agent
sees — never leaked into the prompt):
    - "low"    -> {"unit"}
    - "medium" -> {"unit", "integration"}
    - "high"   -> {"unit", "integration", "e2e", "security"}
`missing` = required(risk_level) - existing_test_plan.

Deterministic: no clock, no randomness, no model call. An empty submission
scores 0.0 (anti-gaming: no reward for degenerate output).
"""

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
    """Return fractional credit in [0.0, 1.0] for one submission."""
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
