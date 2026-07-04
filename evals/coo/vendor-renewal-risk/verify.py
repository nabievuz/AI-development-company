"""Deterministic verifier — coo / vendor-renewal-risk.

Fractional credit rewards true positives and penalises false positives:

    credit = clamp01( (|reported ∩ at_risk| - |reported \\ at_risk|) / |at_risk| )

The at-risk set is derived from the SAME vendor register the agent was given —
applying the stated criteria correctly reproduces it — so nothing is leaked:
the fixture is the input, and grading it is the graded skill. Deterministic
(no clock/model). An empty submission scores 0.0.
"""

from __future__ import annotations

import json
from pathlib import Path

_SLA_BREACH_THRESHOLD = 2
_COST_CHANGE_THRESHOLD = 20


def _at_risk(fixtures: Path) -> set[str]:
    data = json.loads((fixtures / "vendors.json").read_text(encoding="utf-8"))
    return {
        str(v.get("name"))
        for v in data.get("vendors", [])
        if v.get("sla_breaches_ytd", 0) >= _SLA_BREACH_THRESHOLD
        or v.get("cost_change_pct", 0) >= _COST_CHANGE_THRESHOLD
    }


def verify(submission: dict, fixtures: Path) -> float:
    """Return fractional credit in [0.0, 1.0] for one submission."""
    expected = _at_risk(fixtures)
    if not expected:
        return 0.0

    reported = submission.get("flagged_vendors", [])
    if not isinstance(reported, list):
        return 0.0
    reported_set = {str(x) for x in reported}

    hits = len(reported_set & expected)
    false_pos = len(reported_set - expected)
    return max(0.0, (hits - false_pos) / len(expected))
