"""Deterministic verifier — cmo / cac-underperformer-flagging.

Fractional credit rewards true positives and penalises false positives:

    credit = clamp01( (|reported ∩ underperforming| - |reported \\ underperforming|) / |underperforming| )

The underperforming-channel set is derived from the SAME fixture the agent
was given — actual CAC (spend / conversions) strictly greater than
`target_cac` — so nothing is leaked into the prompt: applying the CAC-vs-target
rule correctly *is* the graded skill. Deterministic (no clock/model). An
empty submission scores 0.0.
"""

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
            # No conversions at all is the worst-case CAC (infinite) — always bad.
            bad.add(str(channel.get("name")))
            continue
        cac = spend / conversions
        if cac > target_cac:
            bad.add(str(channel.get("name")))
    return bad


def verify(submission: dict, fixtures: Path) -> float:
    """Return fractional credit in [0.0, 1.0] for one submission."""
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
