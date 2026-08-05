
from __future__ import annotations

import re
from pathlib import Path


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
