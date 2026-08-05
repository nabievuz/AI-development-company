
from __future__ import annotations

from pathlib import Path


ACCEPTED_FIXES = frozenset({"inject_clock", "freeze_time", "assert_range"})


_FLAKY_MARKER = "datetime.datetime.now()"


def verify(submission: dict, fixtures: Path) -> float:
    credit = 0.0

    src = (fixtures / "sample_test.py").read_text(encoding="utf-8").splitlines()
    line = submission.get("flaky_line")
    if (
        isinstance(line, int)
        and not isinstance(line, bool)
        and 1 <= line <= len(src)
        and _FLAKY_MARKER in src[line - 1]
    ):
        credit += 0.5

    fix = str(submission.get("fix_kind", "")).strip().lower()
    if fix in ACCEPTED_FIXES:
        credit += 0.5

    return credit
