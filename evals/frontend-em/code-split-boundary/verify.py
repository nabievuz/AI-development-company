"""Deterministic verifier — frontend-em / code-split-boundary.

Fractional credit rewards true positives and penalises false positives:

    credit = clamp01( (|reported ∩ splittable| - |reported \\ splittable|) / |splittable| )

The splittable set is derived from the SAME route report the agent was given
(initial_bundle_kb > 150 AND not is_critical_path) — doing the architecture
call correctly reproduces it, so nothing is leaked: the fixture is the input,
and grading it is the graded skill. Deterministic (no clock/model). An empty
submission scores 0.0.
"""

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
    """Return fractional credit in [0.0, 1.0] for one submission."""
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
