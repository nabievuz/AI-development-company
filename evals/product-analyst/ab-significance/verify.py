from __future__ import annotations

import json
import math
from pathlib import Path


def _analyse(fixtures: Path) -> tuple[bool, str]:
    data = json.loads((fixtures / "experiment.json").read_text(encoding="utf-8"))
    c, v = data["control"], data["variant"]
    p1, p2 = c["conversions"] / c["n"], v["conversions"] / v["n"]
    pooled = (c["conversions"] + v["conversions"]) / (c["n"] + v["n"])
    se = math.sqrt(pooled * (1 - pooled) * (1 / c["n"] + 1 / v["n"]))
    z = 0.0 if se == 0 else (p2 - p1) / se
    winner = "variant" if p2 > p1 else ("control" if p1 > p2 else "tie")
    return abs(z) > 1.96, winner


def verify(submission: dict, fixtures: Path) -> float:
    sig, winner = _analyse(fixtures)
    credit = 0.0
    if submission.get("significant") is sig:
        credit += 0.5
    if str(submission.get("winner", "")).strip().lower() == winner:
        credit += 0.5
    return credit
