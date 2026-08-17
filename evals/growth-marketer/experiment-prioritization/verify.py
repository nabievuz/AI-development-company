from __future__ import annotations

import json
from pathlib import Path

_SCORE_TOLERANCE = 0.5


def _analyse(fixtures: Path) -> tuple[str, float]:
    experiments = json.loads(
        (fixtures / "experiments.json").read_text(encoding="utf-8")
    )["experiments"]
    best_name = None
    best_score = -1.0
    for exp in experiments:
        effort = exp["effort"]
        if effort <= 0:
            continue
        rice = (exp["reach"] * exp["impact"] * exp["confidence"]) / effort
        if rice > best_score:
            best_score = rice
            best_name = exp["name"]
    return str(best_name), float(best_score)


def verify(submission: dict, fixtures: Path) -> float:
    expected_name, expected_score = _analyse(fixtures)
    credit = 0.0
    if str(submission.get("top_experiment", "")).strip() == expected_name:
        credit += 0.5
    score = submission.get("rice_score")
    if isinstance(score, int | float) and abs(float(score) - expected_score) <= _SCORE_TOLERANCE:
        credit += 0.5
    return credit
