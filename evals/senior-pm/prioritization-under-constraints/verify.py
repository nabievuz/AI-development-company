from __future__ import annotations

import itertools
import json
from pathlib import Path


def _load(fixtures: Path) -> tuple[int, dict[str, dict]]:
    data = json.loads((fixtures / "backlog.json").read_text(encoding="utf-8"))
    capacity = int(data["capacity_weeks"])
    items = {it["id"]: it for it in data["items"]}
    return capacity, items


def _feasible(selected: set[str], capacity: int, items: dict[str, dict]) -> bool:
    if not selected:
        return True
    if any(sid not in items for sid in selected):
        return False
    effort = sum(items[sid]["effort_weeks"] for sid in selected)
    if effort > capacity:
        return False
    for sid in selected:
        for dep in items[sid].get("depends_on", []):
            if dep not in selected:
                return False
    return True


def _value(selected: set[str], items: dict[str, dict]) -> float:
    return sum(items[sid]["value"] for sid in selected if sid in items)


def _optimal_value(capacity: int, items: dict[str, dict]) -> float:
    ids = list(items.keys())
    best = 0.0
    for r in range(len(ids) + 1):
        for combo in itertools.combinations(ids, r):
            combo_set = set(combo)
            if _feasible(combo_set, capacity, items):
                best = max(best, _value(combo_set, items))
    return best


def verify(submission: dict, fixtures: Path) -> float:
    capacity, items = _load(fixtures)
    selected = submission.get("selected", [])
    if not isinstance(selected, list):
        return 0.0
    selected_set = {str(s) for s in selected}

    if not selected_set:
        return 0.0
    if not _feasible(selected_set, capacity, items):
        return 0.0

    achieved = _value(selected_set, items)
    optimal = _optimal_value(capacity, items)
    if optimal <= 0:
        return 0.0
    return max(0.0, min(1.0, achieved / optimal))
