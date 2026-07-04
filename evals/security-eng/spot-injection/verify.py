"""Deterministic verifier — security-eng / spot-injection."""
from __future__ import annotations

from pathlib import Path

_SQL_KEYWORDS = ("select", "insert", "update", "delete")
_ACCEPTED_TYPES = frozenset({"sql_injection", "sqli"})


def _vuln_line(src_lines: list[str]) -> int | None:
    for i, line in enumerate(src_lines, start=1):
        low = line.lower()
        if 'f"' in low or "f'" in low or " % " in low or '" +' in low:
            if any(k in low for k in _SQL_KEYWORDS):
                return i
    return None


def verify(submission: dict, fixtures: Path) -> float:
    lines = (fixtures / "query.py").read_text(encoding="utf-8").splitlines()
    expected = _vuln_line(lines)
    credit = 0.0
    line = submission.get("vuln_line")
    if (
        isinstance(line, int)
        and not isinstance(line, bool)
        and expected is not None
        and line == expected
    ):
        credit += 0.5
    if str(submission.get("vuln_type", "")).strip().lower() in _ACCEPTED_TYPES:
        credit += 0.5
    return credit
