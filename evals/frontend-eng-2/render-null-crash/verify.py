"""Deterministic verifier — frontend-eng-2 / render-null-crash.

Fractional credit:
  * 0.5 if bug_line points at the line with the unguarded `.map(` call in the
    fixture (the buggy line is located by scanning the actual fixture source —
    it is never hardcoded independently of it).
  * 0.5 if fix_kind names an accepted null-safety fix strategy.

Deterministic: no clock, no randomness, no model call. An empty submission
scores 0.0 (anti-gaming: no reward for degenerate output).
"""

from __future__ import annotations

from pathlib import Path

#: Fix strategies that make an unguarded `.map(` over a possibly-missing prop safe.
ACCEPTED_FIXES = frozenset({"optional_chaining", "default_prop_value", "early_return_guard"})


def _bug_line(src: list[str]) -> int | None:
    for i, line in enumerate(src, start=1):
        if ".map(" in line and "?.map(" not in line:
            return i
    return None


def verify(submission: dict, fixtures: Path) -> float:
    """Return fractional credit in [0.0, 1.0] for one submission."""
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
