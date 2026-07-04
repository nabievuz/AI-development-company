"""Deterministic verifier — seo-specialist / broken-canonical-audit.

Fractional credit rewards true positives and penalises false positives:

    credit = clamp01( (|reported ∩ broken| - |reported \\ broken|) / |broken| )

The broken-page set is derived from the SAME crawl the agent was given — a
canonical is broken when missing/empty, or when it points to a URL that never
appears elsewhere in the crawl (a dangling canonical) — so nothing is leaked
into the prompt: applying the check correctly *is* the graded skill.
Deterministic (no clock/model). An empty submission scores 0.0.
"""

from __future__ import annotations

import json
from pathlib import Path


def _broken(fixtures: Path) -> set[str]:
    data = json.loads((fixtures / "pages.json").read_text(encoding="utf-8"))
    pages = data.get("pages", [])
    known_urls = {str(p.get("url")) for p in pages}

    broken: set[str] = set()
    for page in pages:
        url = str(page.get("url"))
        canonical = str(page.get("canonical", "")).strip()
        if not canonical:
            broken.add(url)
            continue
        if canonical != url and canonical not in known_urls:
            broken.add(url)
    return broken


def verify(submission: dict, fixtures: Path) -> float:
    """Return fractional credit in [0.0, 1.0] for one submission."""
    expected = _broken(fixtures)
    if not expected:
        return 0.0

    reported = submission.get("broken_urls", [])
    if not isinstance(reported, list):
        return 0.0
    reported_set = {str(x) for x in reported}

    hits = len(reported_set & expected)
    false_pos = len(reported_set - expected)
    return max(0.0, (hits - false_pos) / len(expected))
