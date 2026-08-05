from __future__ import annotations

import json
from pathlib import Path

_THRESHOLD = 0.05


def verify(submission: dict, fixtures: Path) -> float:
    values = json.loads((fixtures / "series.json").read_text(encoding="utf-8"))["values"]
    net = values[-1] - values[0]
    drift = abs(net) >= _THRESHOLD
    direction = "down" if net < 0 else "up"
    credit = 0.0
    if submission.get("drift_detected") is drift:
        credit += 0.5
    if drift and str(submission.get("direction", "")).strip().lower() == direction:
        credit += 0.5
    return credit
