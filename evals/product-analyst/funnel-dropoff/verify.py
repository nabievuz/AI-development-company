from __future__ import annotations

import json
from pathlib import Path


def _worst_step(fixtures: Path) -> str:
    steps = json.loads((fixtures / "funnel.json").read_text(encoding="utf-8"))["steps"]
    worst, worst_rel = None, -1.0
    for prev, cur in zip(steps, steps[1:]):
        prev_c = prev["count"]
        if prev_c <= 0:
            continue
        rel = (prev_c - cur["count"]) / prev_c
        if rel > worst_rel:
            worst, worst_rel = cur["name"], rel
    return str(worst)


def verify(submission: dict, fixtures: Path) -> float:
    expected = _worst_step(fixtures)
    return 1.0 if submission.get("biggest_dropoff_step") == expected else 0.0
