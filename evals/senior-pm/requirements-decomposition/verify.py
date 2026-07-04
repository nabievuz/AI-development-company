"""Deterministic verifier — senior-pm / requirements-decomposition.

The stakeholder thread in ``fixtures/stakeholder-thread.md`` bundles four
independent, atomic requirements. Each is defined here as a set of keywords
that MUST all appear (case-insensitive substring match) in a submitted
requirement string for it to count as "covering" that atomic requirement.
Requiring ALL keywords (an AND, not an OR) blocks trivial single-word
matches from earning credit for genuine decomposition.

credit = clamp01( (covered - padding_penalty) / total_atomic_requirements )

An empty/missing ``requirements`` list scores 0.0.
"""
from __future__ import annotations

from pathlib import Path

# The answer key: NOT present in fixtures/, only here.
_ATOMIC_REQUIREMENTS: list[dict] = [
    {"id": "csv_export", "keywords": ["csv"]},
    {"id": "pdf_export", "keywords": ["pdf"]},
    {"id": "gdpr_export_deletion", "keywords": ["gdpr", "delet"]},
    {"id": "large_export_admin_alert", "keywords": ["admin", "10"]},
]


def _covers(text: str, keywords: list[str]) -> bool:
    lowered = text.lower()
    return all(kw.lower() in lowered for kw in keywords)


def verify(submission: dict, fixtures: Path) -> float:  # noqa: ARG001
    total = len(_ATOMIC_REQUIREMENTS)
    reqs = submission.get("requirements")
    if not isinstance(reqs, list) or not reqs:
        return 0.0
    strings = [str(r) for r in reqs if isinstance(r, (str, int, float))]
    if not strings:
        return 0.0

    covered = 0
    for atomic in _ATOMIC_REQUIREMENTS:
        if any(_covers(s, atomic["keywords"]) for s in strings):
            covered += 1

    # Padding penalty: submitting far more candidates than atomic requirements
    # (e.g. one sentence per possible keyword) shouldn't be a free way to farm
    # coverage. No penalty until the list is more than 2x the atomic count.
    excess = max(0, len(strings) - 2 * total)
    credit = (covered - excess) / total
    return max(0.0, min(1.0, credit))
