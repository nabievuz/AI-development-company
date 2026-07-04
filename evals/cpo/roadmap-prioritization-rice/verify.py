"""Deterministic verifier — cpo / roadmap-prioritization-rice.

Computes RICE = (reach * impact * confidence) / effort_weeks for every
candidate feature, then brute-forces the capacity-feasible subset with the
maximum total RICE value (n is small, so 2**n subsets is cheap and exact).

credit = 0.0                                   if submission violates capacity
credit = clamp01(achieved_value / optimal_value) otherwise

Deterministic (no clock/model/randomness). An empty submission scores 0.0.
The optimal subset is derived here only — never spelled out in fixtures/task.md.
"""

from __future__ import annotations

import itertools
import json
from pathlib import Path


def _load(fixtures: Path) -> tuple[int, dict[str, tuple[float, int]]]:
    data = json.loads((fixtures / "features.json").read_text(encoding="utf-8"))
    capacity = int(data["capacity_weeks"])
    features: dict[str, tuple[float, int]] = {}
    for f in data.get("features", []):
        name = str(f["name"])
        rice = (float(f["reach"]) * float(f["impact"]) * float(f["confidence"])) / float(
            f["effort_weeks"]
        )
        features[name] = (rice, int(f["effort_weeks"]))
    return capacity, features


def _optimal_value(capacity: int, features: dict[str, tuple[float, int]]) -> float:
    names = list(features)
    best = 0.0
    for r in range(len(names) + 1):
        for combo in itertools.combinations(names, r):
            effort = sum(features[n][1] for n in combo)
            if effort > capacity:
                continue
            value = sum(features[n][0] for n in combo)
            best = max(best, value)
    return best


def verify(submission: dict, fixtures: Path) -> float:
    """Return fractional credit in [0.0, 1.0] for one submission."""
    capacity, features = _load(fixtures)
    optimal_value = _optimal_value(capacity, features)
    if optimal_value <= 0:
        return 0.0

    selected = submission.get("selected", [])
    if not isinstance(selected, list):
        return 0.0
    selected_names = [str(n) for n in selected if str(n) in features]
    if not selected_names:
        return 0.0

    total_effort = sum(features[n][1] for n in selected_names)
    if total_effort > capacity:
        return 0.0

    achieved_value = sum(features[n][0] for n in selected_names)
    return max(0.0, min(1.0, achieved_value / optimal_value))
