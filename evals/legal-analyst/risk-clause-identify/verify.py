from __future__ import annotations

import re
from pathlib import Path

_RISK = re.compile(
    r"without (?:a )?(?:limit|cap)|uncapped|not be limited|not be capped|"
    r"no cap on liability|unlimited liability",
    re.IGNORECASE,
)
_LINE_NUM = re.compile(r"^\s*(\d+)\.")
_ACCEPTED_CATEGORY = frozenset(
    {"liability", "unlimited_liability", "uncapped_liability", "limitation_of_liability"}
)


def _risk_clause(lines: list[str]) -> int | None:
    for line in lines:
        if _RISK.search(line):
            match = _LINE_NUM.match(line)
            if match:
                return int(match.group(1))
    return None


def verify(submission: dict, fixtures: Path) -> float:
    lines = (fixtures / "clauses.txt").read_text(encoding="utf-8").splitlines()
    expected = _risk_clause(lines)

    credit = 0.0
    clause = submission.get("risk_clause")
    if (
        isinstance(clause, int)
        and not isinstance(clause, bool)
        and expected is not None
        and clause == expected
    ):
        credit += 0.5
    if str(submission.get("risk_category", "")).strip().lower() in _ACCEPTED_CATEGORY:
        credit += 0.5
    return credit
