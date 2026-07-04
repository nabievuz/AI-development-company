"""Deterministic verifier — ux-researcher / insight-vs-noise.

Fractional credit rewards true positives and penalises false positives:

    credit = clamp01( (|reported ∩ insights| - |reported \\ insights|) / |insights| )

A quote's topic is an "insight" iff two or more DISTINCT participants raised it
in the same fixture the agent was given — the answer key is derived from the
input, never leaked separately. Deterministic (no clock/model). An empty
submission scores 0.0.
"""

from __future__ import annotations

import json
from pathlib import Path


def _insight_quote_ids(fixtures: Path) -> set[str]:
    data = json.loads((fixtures / "quotes.json").read_text(encoding="utf-8"))
    quotes = data.get("quotes", [])

    participants_by_topic: dict[str, set[str]] = {}
    for q in quotes:
        topic = q.get("topic")
        participant = q.get("participant")
        participants_by_topic.setdefault(topic, set()).add(participant)

    insight_topics = {
        topic for topic, participants in participants_by_topic.items()
        if len(participants) >= 2
    }
    return {str(q.get("id")) for q in quotes if q.get("topic") in insight_topics}


def verify(submission: dict, fixtures: Path) -> float:
    """Return fractional credit in [0.0, 1.0] for one submission."""
    expected = _insight_quote_ids(fixtures)
    if not expected:
        return 0.0

    reported = submission.get("insights", [])
    if not isinstance(reported, list):
        return 0.0
    reported_set = {str(x) for x in reported}

    hits = len(reported_set & expected)
    false_pos = len(reported_set - expected)
    return max(0.0, (hits - false_pos) / len(expected))
