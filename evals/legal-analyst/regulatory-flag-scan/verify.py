"""Deterministic verifier — legal-analyst / regulatory-flag-scan.

Fractional credit rewards true positives and penalises false positives:

    credit = clamp01( (|reported ∩ missing| - |reported \\ missing|) / |missing| )

The "missing" set is derived by scanning the SAME privacy-policy fixture the
agent was given for substantive coverage of each checklist disclosure — doing
the task correctly reproduces it, so nothing is leaked beyond the checklist
itself (already spelled out in task.md). Deterministic (no clock/model). An
empty submission scores 0.0.
"""

from __future__ import annotations

import re
from pathlib import Path

# disclosure ID -> regex patterns that indicate the disclosure is substantively
# present in the policy text.
_REQUIRED_DISCLOSURES: dict[str, str] = {
    "legal_basis": r"legal basis",
    "right_to_access": r"right to access|access to your data|request a copy of",
    "right_to_erasure": r"right to erasure|right to be forgotten|delete your (?:personal )?data",
    "consent_withdrawal": r"withdraw(?:ing)?.*consent",
    "breach_notification_72h": r"72 hours|breach notification|data breach",
    "dpo_contact": r"data protection officer|\bdpo\b",
    "retention_period": r"retention period|how long we (?:keep|retain)|we retain your data for",
    "cross_border_transfer": (
        r"cross-border|international transfer|third country|"
        r"outside the (?:eu|european economic area|eea)"
    ),
}


def _missing_disclosures(fixtures: Path) -> set[str]:
    text = (fixtures / "privacy-policy.md").read_text(encoding="utf-8")
    return {
        disclosure_id
        for disclosure_id, pattern in _REQUIRED_DISCLOSURES.items()
        if not re.search(pattern, text, re.IGNORECASE)
    }


def verify(submission: dict, fixtures: Path) -> float:
    """Return fractional credit in [0.0, 1.0] for one submission."""
    expected = _missing_disclosures(fixtures)
    if not expected:
        return 0.0

    reported = submission.get("missing_disclosures", [])
    if not isinstance(reported, list):
        return 0.0
    reported_set = {str(x) for x in reported}

    hits = len(reported_set & expected)
    false_pos = len(reported_set - expected)
    return max(0.0, (hits - false_pos) / len(expected))
