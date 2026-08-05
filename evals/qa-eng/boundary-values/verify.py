from __future__ import annotations

import json
from pathlib import Path


def verify(submission: dict, fixtures: Path) -> float:
    data = json.loads((fixtures / "spec.json").read_text(encoding="utf-8"))
    lo = int(data["params"]["lo"])
    hi = int(data["params"]["hi"])
    required = {lo - 1, lo, hi, hi + 1}
    cases = submission.get("cases")
    if not isinstance(cases, list):
        return 0.0
    got = {c for c in cases if isinstance(c, int) and not isinstance(c, bool)}
    hits = len(got & required)
    false_pos = len(got - required)
    return max(0.0, (hits - false_pos) / len(required))
