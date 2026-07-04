"""Deterministic verifier — coo / sla-gate-decision.

Two-part credit:

  0.5 for the correct boolean release-gate decision.
  0.5 for the correct blocking-issue id set, scored the same way as
      coverage-gap/vendor-renewal-risk (true-positive minus false-positive,
      normalised), except when the true blocking set is empty — then this
      half is all-or-nothing (an empty ``blocking_issues`` is required).

Both the decision and the blocking set are derived from the SAME compliance
report the agent was given — applying the stated gate rule correctly
reproduces them — so nothing is leaked. Deterministic (no clock/model). An
empty submission scores 0.0.
"""

from __future__ import annotations

import json
from pathlib import Path

_BLOCKING_SEVERITIES = {"critical", "high"}


def _blocking_ids(fixtures: Path) -> set[str]:
    data = json.loads((fixtures / "compliance_report.json").read_text(encoding="utf-8"))
    return {
        str(issue.get("id"))
        for issue in data.get("issues", [])
        if issue.get("resolved") is False
        and str(issue.get("severity", "")).lower() in _BLOCKING_SEVERITIES
    }


def verify(submission: dict, fixtures: Path) -> float:
    """Return fractional credit in [0.0, 1.0] for one submission."""
    expected_ids = _blocking_ids(fixtures)
    expected_block = bool(expected_ids)

    credit = 0.0
    if submission.get("block_release") is expected_block:
        credit += 0.5

    reported = submission.get("blocking_issues", [])
    if not isinstance(reported, list):
        reported = []
    reported_set = {str(x) for x in reported}

    if expected_ids:
        hits = len(reported_set & expected_ids)
        false_pos = len(reported_set - expected_ids)
        credit += 0.5 * max(0.0, (hits - false_pos) / len(expected_ids))
    elif not reported_set:
        credit += 0.5

    return max(0.0, min(1.0, credit))
