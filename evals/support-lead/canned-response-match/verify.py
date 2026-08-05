from __future__ import annotations

import json
from pathlib import Path


_ANSWERS = {
    "M-1": "TPL-REFUND",
    "M-2": "TPL-PWRESET",
    "M-3": "TPL-BUG-ACK",
    "M-4": "TPL-FEATURE-ACK",
    "M-5": "TPL-GENERAL",
}


def verify(submission: dict, fixtures: Path) -> float:
    messages = json.loads((fixtures / "messages.json").read_text(encoding="utf-8"))["messages"]
    answers = submission.get("answers")
    if not isinstance(answers, dict) or not messages:
        return 0.0

    correct = 0
    for message in messages:
        mid = message["id"]
        if answers.get(mid) == _ANSWERS[mid]:
            correct += 1
    return correct / len(messages)
