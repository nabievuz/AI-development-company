"""Deterministic verifier — cdo / contrast-gate.

Fractional credit rewards true positives and penalises false positives:

    credit = clamp01( (|reported ∩ failing| - |reported \\ failing|) / |failing| )

The failing set is derived by applying the WCAG 2.1 Level AA thresholds
(4.5:1 normal text, 3.0:1 large text) to the SAME ratios the agent was given —
correctly applying the AA rule reproduces it, so nothing is leaked: the
fixture (ratio + text size) is the input, and grading it against the AA rule
is the graded skill. Deterministic (no clock/model). An empty submission
scores 0.0.
"""

from __future__ import annotations

import json
from pathlib import Path

_AA_NORMAL = 4.5
_AA_LARGE = 3.0


def _failing(fixtures: Path) -> set[str]:
    data = json.loads((fixtures / "pairs.json").read_text(encoding="utf-8"))
    out: set[str] = set()
    for pair in data.get("pairs", []):
        ratio = float(pair.get("ratio", 0.0))
        size = pair.get("text_size", "normal")
        bar = _AA_LARGE if size == "large" else _AA_NORMAL
        if ratio < bar:
            out.add(str(pair.get("name")))
    return out


def verify(submission: dict, fixtures: Path) -> float:
    """Return fractional credit in [0.0, 1.0] for one submission."""
    expected = _failing(fixtures)
    if not expected:
        return 0.0

    reported = submission.get("failing", [])
    if not isinstance(reported, list):
        return 0.0
    reported_set = {str(x) for x in reported}

    hits = len(reported_set & expected)
    false_pos = len(reported_set - expected)
    return max(0.0, (hits - false_pos) / len(expected))
