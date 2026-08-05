from __future__ import annotations

import json
from itertools import combinations
from pathlib import Path


def _priority_score(item: dict) -> float:
    return 2 * item["impact"] + 1.5 * item["urgency"] - 1 * item["effort"]


def verify(submission: dict, fixtures: Path) -> float:
    data = json.loads((fixtures / "backlog.json").read_text(encoding="utf-8"))
    items = data["items"]

    scored = sorted(items, key=lambda it: _priority_score(it), reverse=True)
    required_order = [it["id"] for it in scored]

    order = submission.get("order")
    if not isinstance(order, list) or not order:
        return 0.0

    position = {item_id: idx for idx, item_id in enumerate(order) if isinstance(item_id, str)}

    pairs = list(combinations(required_order, 2))
    if not pairs:
        return 0.0

    concordant = 0
    for higher, lower in pairs:
        if higher in position and lower in position and position[higher] < position[lower]:
            concordant += 1

    return max(0.0, min(1.0, concordant / len(pairs)))
