
from __future__ import annotations

import json
from pathlib import Path

_AA_NORMAL = 4.5
_AA_LARGE = 3.0


def _failing(fixtures: Path) -> set[str]:
    data = json.loads((fixtures / "pairs.json").read_text(encoding="utf-8"))
    out: set[str] = set()
    for pair in data.get("pairs", []):
        ratio = float(pair.get("ratio", 0.0))
        size = pair.get("text_size", "normal")
        bar = _AA_LARGE if size == "large" else _AA_NORMAL
        if ratio < bar:
            out.add(str(pair.get("name")))
    return out


def verify(submission: dict, fixtures: Path) -> float:
    expected = _failing(fixtures)
    if not expected:
        return 0.0

    reported = submission.get("failing", [])
    if not isinstance(reported, list):
        return 0.0
    reported_set = {str(x) for x in reported}

    hits = len(reported_set & expected)
    false_pos = len(reported_set - expected)
    return max(0.0, (hits - false_pos) / len(expected))
