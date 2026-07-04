"""Deterministic verifier — qa-eng / detect-flaky-assertion.

Fractional credit:
  * 0.5 if flaky_line points at the assertion that reads datetime.datetime.now()
    in the fixture (checked against the actual fixture source, not a hardcoded
    number — the answer key is derived from the input, never leaked into it).
  * 0.5 if fix_kind is an accepted deterministic-time fix strategy.

Deterministic: no clock, no randomness, no model call. An empty submission
scores 0.0 (anti-gaming: no reward for degenerate output).
"""

from __future__ import annotations

from pathlib import Path

#: Fix strategies that make a wall-clock assertion deterministic.
ACCEPTED_FIXES = frozenset({"inject_clock", "freeze_time", "assert_range"})

#: The non-deterministic call the flaky assertion must reference.
_FLAKY_MARKER = "datetime.datetime.now()"


def verify(submission: dict, fixtures: Path) -> float:
    """Return fractional credit in [0.0, 1.0] for one submission."""
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
