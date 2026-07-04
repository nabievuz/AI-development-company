"""Deterministic verifier — cmo / brand-voice-violation-audit.

Fractional credit rewards true positives and penalises false positives:

    credit = clamp01( (|reported ∩ violations| - |reported \\ violations|) / |violations| )

The violation set is derived from the SAME fixture the agent was given by
applying the three brand-voice rules stated in the prompt (banned
superlative phrase / multiple exclamation marks / all-caps shouting word) —
nothing beyond those rules is leaked. Deterministic (no clock/model). An
empty submission scores 0.0.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

BANNED_PHRASES = (
    "best ever",
    "guaranteed",
    "revolutionary",
    "#1",
    "life-changing",
)

_WORD_RE = re.compile(r"[A-Za-z]+")


def _has_banned_phrase(text_lower: str) -> bool:
    return any(phrase in text_lower for phrase in BANNED_PHRASES)


def _has_multi_exclamation(text: str) -> bool:
    return text.count("!") > 1


def _has_shouting_word(text: str) -> bool:
    for match in _WORD_RE.finditer(text):
        word = match.group(0)
        if len(word) >= 4 and word.isupper():
            return True
    return False


def _violations(fixtures: Path) -> set[str]:
    data = json.loads((fixtures / "snippets.json").read_text(encoding="utf-8"))
    bad: set[str] = set()
    for snippet in data.get("snippets", []):
        text = str(snippet.get("text", ""))
        text_lower = text.lower()
        if (
            _has_banned_phrase(text_lower)
            or _has_multi_exclamation(text)
            or _has_shouting_word(text)
        ):
            bad.add(str(snippet.get("id")))
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
