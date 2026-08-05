from __future__ import annotations

import json
from pathlib import Path

STATUS = {
    "resource_not_found": 404,
    "unauthenticated": 401,
    "forbidden": 403,
    "created": 201,
    "conflict": 409,
    "bad_input": 400,
    "ok": 200,
    "no_content": 204,
}


def verify(submission: dict, fixtures: Path) -> float:
    scenarios = json.loads(
        (fixtures / "scenarios.json").read_text(encoding="utf-8")
    )["scenarios"]
    answers = submission.get("statuses")
    if not isinstance(answers, dict) or not scenarios:
        return 0.0
    correct = 0
    for sc in scenarios:
        expected = STATUS.get(sc["situation"])
        if expected is not None and answers.get(sc["id"]) == expected:
            correct += 1
    return correct / len(scenarios)
