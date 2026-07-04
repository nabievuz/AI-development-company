"""Deterministic verifier — qa-lead / review-triage.

Fractional credit rewards true positives and penalises false positives:

    credit = clamp01( (|reported ∩ blocking| - |reported \\ blocking|) / |blocking| )

Blocking-merge rule (derived from the SAME fixture the agent sees — never
leaked into the prompt): a finding blocks the merge iff its severity is
`blocker`, OR its severity is `major` AND its category is `security`. A
`major`/non-security finding (e.g. a major style nit) does NOT block — this is
the triage-judgment probe: severity alone is not sufficient.

Deterministic: no clock, no randomness, no model call. An empty submission
scores 0.0 (anti-gaming: no reward for degenerate output).
"""

from __future__ import annotations

import json
from pathlib import Path


def _blocking(fixtures: Path) -> set[str]:
    data = json.loads((fixtures / "findings.json").read_text(encoding="utf-8"))
    blocking = set()
    for f in data.get("findings", []):
        severity = f.get("severity")
        if severity == "blocker" or (severity == "major" and f.get("category") == "security"):
            blocking.add(str(f.get("id")))
    return blocking


def verify(submission: dict, fixtures: Path) -> float:
    """Return fractional credit in [0.0, 1.0] for one submission."""
    expected = _blocking(fixtures)
    if not expected:
        return 0.0

    reported = submission.get("blocking", [])
    if not isinstance(reported, list):
        return 0.0
    reported_set = {str(x) for x in reported}

    hits = len(reported_set & expected)
    false_pos = len(reported_set - expected)
    return max(0.0, (hits - false_pos) / len(expected))
