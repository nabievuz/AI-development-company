
from __future__ import annotations

import json
from pathlib import Path

_RULES = (
    ("has_confirmation_on_destructive_action", False, "error_prevention"),
    ("shows_loading_indicator", False, "visibility_of_system_status"),
    ("error_messages_generic", True, "help_users_recognize_diagnose_recover"),
    ("consistent_button_placement", False, "consistency_and_standards"),
)


def _violations(fixtures: Path) -> set[str]:
    data = json.loads((fixtures / "screen_audit.json").read_text(encoding="utf-8"))
    return {
        code
        for field, bad_value, code in _RULES
        if data.get(field) is bad_value
    }


def verify(submission: dict, fixtures: Path) -> float:
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
