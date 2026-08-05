from __future__ import annotations

import re
from pathlib import Path

_SECRET = re.compile(r"sk-[A-Za-z0-9-]{8,}|AKIA[0-9A-Z]{8,}|password\s*=", re.I)
_ACCEPTED_KIND = frozenset({"api_key", "secret", "credential", "token"})


def _secret_line(diff_lines: list[str]) -> int | None:
    for i, line in enumerate(diff_lines, start=1):
        if line.startswith("+") and not line.startswith("+++"):
            if _SECRET.search(line):
                return i
    return None


def verify(submission: dict, fixtures: Path) -> float:
    lines = (fixtures / "change.diff").read_text(encoding="utf-8").splitlines()
    expected = _secret_line(lines)
    credit = 0.0
    line = submission.get("secret_line")
    if (
        isinstance(line, int)
        and not isinstance(line, bool)
        and expected is not None
        and line == expected
    ):
        credit += 0.5
    if str(submission.get("kind", "")).strip().lower() in _ACCEPTED_KIND:
        credit += 0.5
    return credit
