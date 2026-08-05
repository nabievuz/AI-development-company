
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
