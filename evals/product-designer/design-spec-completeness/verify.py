
from __future__ import annotations

import json
from pathlib import Path

REQUIRED_STATES = frozenset({"default", "hover", "focus", "disabled", "error"})
REQUIRED_A11Y = frozenset({"aria_label", "focus_visible"})


def _missing(fixtures: Path) -> set[str]:
    data = json.loads((fixtures / "component_spec.json").read_text(encoding="utf-8"))
    present_states = set(data.get("states", {}).keys())
    present_a11y = set(data.get("a11y", {}).keys())
    missing = {f"state:{s}" for s in REQUIRED_STATES - present_states}
    missing |= {f"a11y:{a}" for a in REQUIRED_A11Y - present_a11y}
    return missing


def verify(submission: dict, fixtures: Path) -> float:
    expected = _missing(fixtures)
    if not expected:
        return 0.0

    reported = submission.get("missing", [])
    if not isinstance(reported, list):
        return 0.0
    reported_set = {str(x) for x in reported}

    hits = len(reported_set & expected)
    false_pos = len(reported_set - expected)
    return max(0.0, (hits - false_pos) / len(expected))
