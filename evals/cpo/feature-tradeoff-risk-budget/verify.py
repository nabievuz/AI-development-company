"""Deterministic verifier — cpo / feature-tradeoff-risk-budget.

Brute-forces every subset of initiatives (n is small) to find the maximum
total expected_value_usd achievable within BOTH the budget and the
high-risk-count cap.

credit = 0.0  if the submission violates the budget or the risk cap
credit = clamp01(achieved_value / optimal_value)  otherwise

Deterministic (no clock/model/randomness). An empty submission scores 0.0.
The optimal set is derived here only — never spelled out in fixtures/task.md.
"""

from __future__ import annotations

import itertools
import json
from pathlib import Path


def _load(fixtures: Path) -> tuple[int, int, dict[str, tuple[int, int, str]]]:
    data = json.loads((fixtures / "initiatives.json").read_text(encoding="utf-8"))
    budget = int(data["budget_usd"])
    max_high_risk = int(data["max_high_risk"])
    initiatives: dict[str, tuple[int, int, str]] = {}
    for i in data.get("initiatives", []):
        name = str(i["name"])
        initiatives[name] = (
            int(i["cost_usd"]),
            int(i["expected_value_usd"]),
            str(i["risk_tier"]),
        )
    return budget, max_high_risk, initiatives


def _feasible(names: list[str], budget: int, max_high_risk: int, initiatives: dict) -> bool:
    cost = sum(initiatives[n][0] for n in names)
    high_risk_count = sum(1 for n in names if initiatives[n][2] == "high")
    return cost <= budget and high_risk_count <= max_high_risk


def _optimal_value(budget: int, max_high_risk: int, initiatives: dict) -> float:
    names = list(initiatives)
    best = 0.0
    for r in range(len(names) + 1):
        for combo in itertools.combinations(names, r):
            combo = list(combo)
            if not _feasible(combo, budget, max_high_risk, initiatives):
                continue
            value = sum(initiatives[n][1] for n in combo)
            best = max(best, value)
    return best


def verify(submission: dict, fixtures: Path) -> float:
    """Return fractional credit in [0.0, 1.0] for one submission."""
    budget, max_high_risk, initiatives = _load(fixtures)
    optimal_value = _optimal_value(budget, max_high_risk, initiatives)
    if optimal_value <= 0:
        return 0.0

    greenlit = submission.get("greenlit", [])
    if not isinstance(greenlit, list):
        return 0.0
    names = [str(n) for n in greenlit if str(n) in initiatives]
    if not names:
        return 0.0

    if not _feasible(names, budget, max_high_risk, initiatives):
        return 0.0

    achieved_value = sum(initiatives[n][1] for n in names)
    return max(0.0, min(1.0, achieved_value / optimal_value))
