"""Deterministic verifier — frontend-eng-2 / responsive-gap.

Fractional credit is the intersection-over-union (IoU) of the submitted
viewport-width range against the required gap range. The required range is
derived by parsing the ACTUAL fixture CSS's `@media` breakpoints (not
hardcoded independently of it) — doing the responsive audit correctly
reproduces it, so nothing is leaked. Deterministic (no clock/model call). An
empty submission scores 0.0 (anti-gaming: no reward for degenerate output);
an oversized/guessed range is penalised by the union term (no reward for
"cover everything").
"""

from __future__ import annotations

import re
from pathlib import Path


def _gap_range(fixtures: Path) -> tuple[int, int] | None:
    css = (fixtures / "styles.css").read_text(encoding="utf-8")
    max_matches = [int(x) for x in re.findall(r"max-width:\s*(\d+)px", css)]
    min_matches = [int(x) for x in re.findall(r"min-width:\s*(\d+)px", css)]
    if not max_matches or not min_matches:
        return None
    lo = max(max_matches) + 1
    hi = min(min_matches) - 1
    if lo > hi:
        return None
    return lo, hi


def verify(submission: dict, fixtures: Path) -> float:
    """Return fractional credit in [0.0, 1.0] for one submission."""
    gap = _gap_range(fixtures)
    if gap is None:
        return 0.0
    lo, hi = gap
    required = set(range(lo, hi + 1))

    br = submission.get("broken_range")
    if not (
        isinstance(br, list)
        and len(br) == 2
        and all(isinstance(x, int) and not isinstance(x, bool) for x in br)
    ):
        return 0.0

    a, b = sorted(br)
    submitted = set(range(a, b + 1))

    union = required | submitted
    if not union:
        return 0.0
    intersection = required & submitted
    return max(0.0, min(1.0, len(intersection) / len(union)))
