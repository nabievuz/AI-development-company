from __future__ import annotations

from pathlib import Path


EXPECTED = [3, 1, 5, 4]


def verify(submission: dict, fixtures: Path) -> float:
    answers = submission.get("answers")
    if not isinstance(answers, list) or not answers:
        return 0.0

    correct = 0
    for i, expected in enumerate(EXPECTED):
        if i < len(answers):
            got = answers[i]
            if isinstance(got, int) and not isinstance(got, bool) and got == expected:
                correct += 1
    return max(0.0, correct / len(EXPECTED))
