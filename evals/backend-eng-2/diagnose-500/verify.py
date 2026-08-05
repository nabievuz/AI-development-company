from __future__ import annotations

import json
from pathlib import Path

ACCEPTED_FIXES = frozenset(
    {"null_check", "guard_clause", "none_check", "defensive_check"}
)


def _document(path: Path) -> str:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return str(payload["document"])


def _diagnose(text: str) -> str:
    lower = text.lower()
    if "nonetype" in lower and "attributeerror" in lower:
        return "null_reference"
    if "deadlock" in lower:
        return "deadlock"
    if "timeout" in lower or "timed out" in lower:
        return "timeout"
    if "uniqueviolation" in lower or "duplicate key" in lower:
        return "race_condition"
    return "unknown"


def verify(submission: dict, fixtures: Path) -> float:
    text = _document(fixtures / "incident.json")
    expected = _diagnose(text)
    credit = 0.0
    root_cause = str(submission.get("root_cause", "")).strip().lower()
    if root_cause == expected:
        credit += 0.5
    fix = str(submission.get("fix", "")).strip().lower()
    if fix in ACCEPTED_FIXES:
        credit += 0.5
    return credit
