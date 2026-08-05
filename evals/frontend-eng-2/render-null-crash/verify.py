
from __future__ import annotations

from pathlib import Path


ACCEPTED_FIXES = frozenset({"optional_chaining", "default_prop_value", "early_return_guard"})


def _bug_line(src: list[str]) -> int | None:
    for i, line in enumerate(src, start=1):
        if ".map(" in line and "?.map(" not in line:
            return i
    return None


def verify(submission: dict, fixtures: Path) -> float:
    credit = 0.0

    src = (fixtures / "UserList.jsx").read_text(encoding="utf-8").splitlines()
    expected_line = _bug_line(src)
    if expected_line is None:
        return 0.0

    line = submission.get("bug_line")
    if (
        isinstance(line, int)
        and not isinstance(line, bool)
        and line == expected_line
    ):
        credit += 0.5

    fix = str(submission.get("fix_kind", "")).strip().lower()
    if fix in ACCEPTED_FIXES:
        credit += 0.5

    return credit
