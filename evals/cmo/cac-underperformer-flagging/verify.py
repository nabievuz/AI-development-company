
from __future__ import annotations

import json
from pathlib import Path


def _underperforming(fixtures: Path) -> set[str]:
    data = json.loads((fixtures / "channels.json").read_text(encoding="utf-8"))
    target_cac = float(data.get("target_cac", 0))
    bad: set[str] = set()
    for channel in data.get("channels", []):
        conversions = float(channel.get("conversions", 0) or 0)
        spend = float(channel.get("spend", 0) or 0)
        if conversions <= 0:

            bad.add(str(channel.get("name")))
            continue
        cac = spend / conversions
        if cac > target_cac:
            bad.add(str(channel.get("name")))
    return bad


def verify(submission: dict, fixtures: Path) -> float:
    expected = _underperforming(fixtures)
    if not expected:
        return 0.0

    reported = submission.get("underperforming_channels", [])
    if not isinstance(reported, list):
        return 0.0
    reported_set = {str(x) for x in reported}

    hits = len(reported_set & expected)
    false_pos = len(reported_set - expected)
    return max(0.0, (hits - false_pos) / len(expected))
