"""Deterministic verifier — frontend-em / component-prop-drilling.

Fractional credit rewards true positives and penalises false positives:

    credit = clamp01( (|reported ∩ flaggable| - |reported \\ flaggable|) / |flaggable| )

The flaggable set is derived from the SAME component report the agent was
given (prop_drill_depth >= 3 AND uses_context is false) — doing the review
correctly reproduces it, so nothing is leaked: the fixture is the input, and
grading it is the graded skill. Deterministic (no clock/model). An empty
submission scores 0.0.
"""

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
    """Return fractional credit in [0.0, 1.0] for one submission."""
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
