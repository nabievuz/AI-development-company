"""Deterministic verifier — design-lead / spacing-grid-audit.

Fractional credit rewards true positives and penalises false positives:

    credit = clamp01( (|reported ∩ violations| - |reported \\ violations|) / |violations| )

The violating set is derived from the SAME spacing spec the agent was given —
applying the design system's grid-gate rule correctly reproduces it, so
nothing is leaked: the fixture is the input, the graded answer key lives only
here. Deterministic (no clock/model). An empty submission scores 0.0.
"""
from __future__ import annotations

import json
from pathlib import Path


def _violations(fixtures: Path) -> set[str]:
    data = json.loads((fixtures / "spacing-spec.json").read_text(encoding="utf-8"))
    base = int(data["grid_base_px"])
    return {
        str(item["token"])
        for item in data.get("spacing", [])
        if int(item["px"]) % base != 0
    }


def verify(submission: dict, fixtures: Path) -> float:
    expected = _violations(fixtures)
    if not expected:
        return 0.0

    reported = submission.get("violations", [])
    if not isinstance(reported, list):
        return 0.0
    reported_set = {str(x) for x in reported}

    hits = len(reported_set & expected)
    false_pos = len(reported_set - expected)
    return max(0.0, (hits - false_pos) / len(expected))
