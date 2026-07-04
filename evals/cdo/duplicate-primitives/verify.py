"""Deterministic verifier — cdo / duplicate-primitives.

Fractional credit rewards true positives and penalises false positives:

    credit = clamp01( (|reported ∩ duplicates| - |reported \\ duplicates|) / |duplicates| )

The duplicate set is derived by grouping the SAME component manifest the agent
was given by its `purpose` field — correctly performing the design-system
consolidation audit reproduces it, so nothing is leaked: the fixture is the
input, and grading it is the graded skill. Deterministic (no clock/model). An
empty submission scores 0.0.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path


def _duplicates(fixtures: Path) -> set[str]:
    data = json.loads((fixtures / "component_manifest.json").read_text(encoding="utf-8"))
    by_purpose: dict[str, list[str]] = defaultdict(list)
    for c in data.get("components", []):
        by_purpose[str(c.get("purpose"))].append(str(c.get("name")))
    out: set[str] = set()
    for names in by_purpose.values():
        if len(names) > 1:
            out.update(names)
    return out


def verify(submission: dict, fixtures: Path) -> float:
    """Return fractional credit in [0.0, 1.0] for one submission."""
    expected = _duplicates(fixtures)
    if not expected:
        return 0.0

    reported = submission.get("duplicates", [])
    if not isinstance(reported, list):
        return 0.0
    reported_set = {str(x) for x in reported}

    hits = len(reported_set & expected)
    false_pos = len(reported_set - expected)
    return max(0.0, (hits - false_pos) / len(expected))
