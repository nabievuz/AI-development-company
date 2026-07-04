"""Deterministic verifier — legal-analyst / missing-clause-check.

Fractional credit rewards true positives and penalises false positives:

    credit = clamp01( (|reported ∩ missing| - |reported \\ missing|) / |missing| )

The "missing" set is derived by scanning the SAME contract fixture the agent was
given for substantive coverage of each checklist clause — doing the task
correctly reproduces it, so nothing is leaked beyond the checklist itself (which
is already spelled out in task.md). Deterministic (no clock/model). An empty
submission scores 0.0.
"""

from __future__ import annotations

import re
from pathlib import Path

# clause ID -> regex patterns that indicate the clause is substantively present.
_REQUIRED_CLAUSES: dict[str, str] = {
    "confidentiality": r"confidential",
    "governing_law": r"governing law",
    "payment_terms": r"fees and payment|payment terms",
    "indemnification": r"indemnif",
    "limitation_of_liability": r"limitation of liability|limit(?:ed|ation)?\s+of\s+liability",
    "data_breach_notification": r"data breach|breach notification",
    "assignment": r"\bassignment\b|subcontract",
    "termination": r"terminat",
}


def _missing_clauses(fixtures: Path) -> set[str]:
    text = (fixtures / "msa.md").read_text(encoding="utf-8")
    return {
        clause_id
        for clause_id, pattern in _REQUIRED_CLAUSES.items()
        if not re.search(pattern, text, re.IGNORECASE)
    }


def verify(submission: dict, fixtures: Path) -> float:
    """Return fractional credit in [0.0, 1.0] for one submission."""
    expected = _missing_clauses(fixtures)
    if not expected:
        return 0.0

    reported = submission.get("missing_clauses", [])
    if not isinstance(reported, list):
        return 0.0
    reported_set = {str(x) for x in reported}

    hits = len(reported_set & expected)
    false_pos = len(reported_set - expected)
    return max(0.0, (hits - false_pos) / len(expected))
