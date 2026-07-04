"""Deterministic verifier — chairman / precedence-adjudication."""
from __future__ import annotations

from pathlib import Path

#: Ground truth per AGENTS.md §2 precedence order, applied to the four
#: scenarios in fixtures/scenarios.json (S1..S4, in order). Lower number wins.
#: S1: dept CLAUDE.md (3) vs role-overlay AGENTS.md (4)      -> 3 wins
#: S2: charter.md (1) vs board-issued governance/ policy (2) -> 1 wins
#: S3: dept AGENTS.md (5) vs root AGENTS.md (6)               -> 5 wins
#: S4: role-overlay AGENTS.md (4) vs dept AGENTS.md (5)       -> 4 wins
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
