"""Deterministic verifier — cdo / raw-hex-audit.

Fractional credit rewards true positives and penalises false positives:

    credit = clamp01( (|reported ∩ raw_hex| - |reported \\ raw_hex|) / |raw_hex| )

The raw-hex set is derived from the SAME style manifest the agent was given —
doing the design-token governance audit correctly reproduces it — so nothing is
leaked: the fixture is the input, and grading it is the graded skill.
Deterministic (no clock/model). An empty submission scores 0.0.
"""

from __future__ import annotations

import json
from pathlib import Path


def _raw_hex(fixtures: Path) -> set[str]:
    data = json.loads((fixtures / "component_styles.json").read_text(encoding="utf-8"))
    return {
        str(c.get("name"))
        for c in data.get("components", [])
        if isinstance(c.get("fill"), dict) and "hex" in c["fill"] and "token" not in c["fill"]
    }


def verify(submission: dict, fixtures: Path) -> float:
    """Return fractional credit in [0.0, 1.0] for one submission."""
    expected = _raw_hex(fixtures)
    if not expected:
        return 0.0

    reported = submission.get("raw_hex", [])
    if not isinstance(reported, list):
        return 0.0
    reported_set = {str(x) for x in reported}

    hits = len(reported_set & expected)
    false_pos = len(reported_set - expected)
    return max(0.0, (hits - false_pos) / len(expected))
