"""Deterministic verifier — seo-specialist / title-meta-length-audit.

Fractional credit rewards true positives and penalises false positives:

    credit = clamp01( (|reported ∩ violations| - |reported \\ violations|) / |violations| )

The violating-page set is derived from the SAME fixture the agent was given —
title length outside [30, 60] chars or meta description length outside
[70, 160] chars — so nothing is leaked into the prompt: applying the length
rule correctly *is* the graded skill. Deterministic (no clock/model). An
empty submission scores 0.0.
"""

from __future__ import annotations

import json
from pathlib import Path

TITLE_MIN, TITLE_MAX = 30, 60
META_MIN, META_MAX = 70, 160


def _violations(fixtures: Path) -> set[str]:
    data = json.loads((fixtures / "pages.json").read_text(encoding="utf-8"))
    bad: set[str] = set()
    for page in data.get("pages", []):
        title_len = len(str(page.get("title", "")))
        meta_len = len(str(page.get("meta_description", "")))
        title_bad = not (TITLE_MIN <= title_len <= TITLE_MAX)
        meta_bad = not (META_MIN <= meta_len <= META_MAX)
        if title_bad or meta_bad:
            bad.add(str(page.get("id")))
    return bad


def verify(submission: dict, fixtures: Path) -> float:
    """Return fractional credit in [0.0, 1.0] for one submission."""
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
