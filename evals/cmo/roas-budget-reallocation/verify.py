"""Deterministic verifier — cmo / roas-budget-reallocation.

Recomputes the correct next-quarter allocation from the SAME fixture the
agent was given, applying the reallocation rule stated in the prompt:
channels below the 2.0 ROAS cutoff are cut to 0; the rest split
``total_budget`` proportionally to their ROAS. Credit is the fraction of
channels the submission gets right within a 5%-of-total_budget tolerance.
Deterministic (no clock/model). An empty submission, or one missing the
``allocations`` object, scores 0.0.
"""

from __future__ import annotations

import json
from pathlib import Path

ROAS_CUTOFF = 2.0
TOLERANCE_FRACTION = 0.05


def _expected_allocations(fixtures: Path) -> dict[str, float]:
    data = json.loads((fixtures / "channels.json").read_text(encoding="utf-8"))
    total_budget = float(data.get("total_budget", 0))
    channels = data.get("channels", [])

    kept = [c for c in channels if float(c.get("roas", 0) or 0) >= ROAS_CUTOFF]
    roas_sum = sum(float(c.get("roas", 0) or 0) for c in kept)

    allocations: dict[str, float] = {}
    for c in channels:
        name = str(c.get("name"))
        roas = float(c.get("roas", 0) or 0)
        if roas < ROAS_CUTOFF or roas_sum <= 0:
            allocations[name] = 0.0
        else:
            allocations[name] = total_budget * roas / roas_sum
    return allocations


def verify(submission: dict, fixtures: Path) -> float:
    """Return fractional credit in [0.0, 1.0] for one submission."""
    data = json.loads((fixtures / "channels.json").read_text(encoding="utf-8"))
    total_budget = float(data.get("total_budget", 0))
    expected = _expected_allocations(fixtures)
    if not expected or total_budget <= 0:
        return 0.0

    reported = submission.get("allocations")
    if not isinstance(reported, dict) or not reported:
        return 0.0

    tolerance = TOLERANCE_FRACTION * total_budget
    correct = 0
    for name, expected_value in expected.items():
        try:
            reported_value = float(reported.get(name))
        except (TypeError, ValueError):
            continue
        if abs(reported_value - expected_value) <= tolerance:
            correct += 1

    return max(0.0, correct / len(expected))
