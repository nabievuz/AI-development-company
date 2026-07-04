"""Deterministic verifier — product-designer / ux-flow-deadends.

A UX dead-end is a non-terminal screen with an empty `transitions` list: a user
who lands there has no way forward, back, or sideways. Terminal screens
(`terminal: true`, e.g. an order-confirmation screen) are the flow's deliberate
exit and are excluded even though they too have no outgoing transitions.

Fractional credit rewards true positives and penalises false positives:

    credit = clamp01( (|reported ∩ dead_ends| - |reported \\ dead_ends|) / |dead_ends| )

The dead-end set is derived from the SAME flow graph the agent was given —
doing the task correctly reproduces it — so nothing is leaked: the fixture is
the input, and grading it is the graded skill. Deterministic (no clock/model).
An empty submission scores 0.0.
"""

from __future__ import annotations

import json
from pathlib import Path


def _dead_ends(fixtures: Path) -> set[str]:
    data = json.loads((fixtures / "flow.json").read_text(encoding="utf-8"))
    return {
        str(screen.get("name"))
        for screen in data.get("screens", [])
        if not screen.get("transitions") and not screen.get("terminal", False)
    }


def verify(submission: dict, fixtures: Path) -> float:
    """Return fractional credit in [0.0, 1.0] for one submission."""
    expected = _dead_ends(fixtures)
    if not expected:
        return 0.0

    reported = submission.get("dead_ends", [])
    if not isinstance(reported, list):
        return 0.0
    reported_set = {str(x) for x in reported}

    hits = len(reported_set & expected)
    false_pos = len(reported_set - expected)
    return max(0.0, (hits - false_pos) / len(expected))
