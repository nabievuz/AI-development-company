
from __future__ import annotations

import json
import re
from pathlib import Path

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


def _document(path: Path) -> str:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return str(payload["document"])


def _missing_disclosures(fixtures: Path) -> set[str]:
    text = _document(fixtures / "privacy_policy.json")
    return {
        disclosure_id
        for disclosure_id, pattern in _REQUIRED_DISCLOSURES.items()
        if not re.search(pattern, text, re.IGNORECASE)
    }


def verify(submission: dict, fixtures: Path) -> float:
    expected = _missing_disclosures(fixtures)
    if not expected:
        raise ValueError(
            "fixture privacy policy is missing no required disclosure — "
            "this task would grade every answer as wrong"
        )

    reported = submission.get("missing_disclosures", [])
    if not isinstance(reported, list):
        return 0.0
    reported_set = {str(x) for x in reported}

    hits = len(reported_set & expected)
    false_pos = len(reported_set - expected)
    return max(0.0, (hits - false_pos) / len(expected))
