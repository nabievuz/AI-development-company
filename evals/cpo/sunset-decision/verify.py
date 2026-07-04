"""Deterministic verifier — cpo / sunset-decision.

A feature is sunset-worthy when BOTH:
  - mau < mau_threshold (low adoption), AND
  - monthly_revenue_usd < maintenance_cost_usd (negative margin)

Fractional credit rewards true positives and penalises false positives:

    credit = clamp01( (|reported ∩ expected| - |reported \\ expected|) / |expected| )

Deterministic (no clock/model/randomness). An empty submission scores 0.0.
The expected set is derived here only — never spelled out in fixtures/task.md.
"""

from __future__ import annotations

import json
from pathlib import Path


def _expected_sunset(fixtures: Path) -> set[str]:
    data = json.loads((fixtures / "feature_usage.json").read_text(encoding="utf-8"))
    threshold = int(data["mau_threshold"])
    expected: set[str] = set()
    for f in data.get("features", []):
        low_adoption = int(f["mau"]) < threshold
        negative_margin = int(f["monthly_revenue_usd"]) < int(f["maintenance_cost_usd"])
        if low_adoption and negative_margin:
            expected.add(str(f["name"]))
    return expected


def verify(submission: dict, fixtures: Path) -> float:
    """Return fractional credit in [0.0, 1.0] for one submission."""
    expected = _expected_sunset(fixtures)
    if not expected:
        return 0.0

    reported = submission.get("sunset", [])
    if not isinstance(reported, list):
        return 0.0
    reported_set = {str(x) for x in reported}

    hits = len(reported_set & expected)
    false_pos = len(reported_set - expected)
    return max(0.0, (hits - false_pos) / len(expected))
