from __future__ import annotations

import json
from pathlib import Path


def _expected_render(scenario: dict) -> str:
    if scenario.get("error"):
        return "ErrorView"
    if scenario.get("loading"):
        return "Spinner"
    if len(scenario.get("items", [])) == 0:
        return "EmptyState"
    return "List"


def verify(submission: dict, fixtures: Path) -> float:
    scenarios = json.loads(
        (fixtures / "scenarios.json").read_text(encoding="utf-8")
    )["scenarios"]

    render = submission.get("render")
    if not isinstance(render, dict) or not scenarios:
        return 0.0

    correct = 0
    for scenario in scenarios:
        expected = _expected_render(scenario)
        got = render.get(scenario["id"])
        if isinstance(got, str) and got.strip() == expected:
            correct += 1
    return correct / len(scenarios)
