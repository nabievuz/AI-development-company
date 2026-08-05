from __future__ import annotations

import json
from pathlib import Path


def verify(submission: dict, fixtures: Path) -> float:
    commits = json.loads((fixtures / "commits.json").read_text(encoding="utf-8"))["commits"]
    cats = submission.get("categories")
    if not isinstance(cats, dict) or not commits:
        return 0.0
    correct = 0
    for c in commits:
        true = c.split(":")[0].strip().lower()
        in_true = isinstance(cats.get(true), list) and c in cats[true]
        in_wrong = any(
            k != true and isinstance(v, list) and c in v for k, v in cats.items()
        )
        if in_true and not in_wrong:
            correct += 1
    return correct / len(commits)
