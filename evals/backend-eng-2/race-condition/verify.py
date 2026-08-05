from __future__ import annotations

from pathlib import Path

ACCEPTED_FIXES = frozenset(
    {
        "lock",
        "mutex",
        "transaction",
        "select_for_update",
        "optimistic_locking",
        "compare_and_swap",
        "unique_constraint",
    }
)

_SYNC_MARKERS = (
    "lock",
    "select_for_update",
    "atomic",
    "transaction",
    "compare_and_swap",
    "mutex",
)

_WRITE_CALLS = (".save(", ".create(", ".insert(", ".update(")


def _has_race_condition(src: str) -> bool:
    lower = src.lower()
    if any(marker in lower for marker in _SYNC_MARKERS):
        return False
    lines = src.splitlines()
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("if "):
            indent = len(line) - len(line.lstrip())
            for nxt in lines[i + 1:]:
                if not nxt.strip():
                    continue
                nxt_indent = len(nxt) - len(nxt.lstrip())
                if nxt_indent <= indent:
                    break
                if any(call in nxt for call in _WRITE_CALLS):
                    return True
    return False


def verify(submission: dict, fixtures: Path) -> float:
    src = (fixtures / "snippet.py").read_text(encoding="utf-8")
    expected = _has_race_condition(src)
    credit = 0.0
    if submission.get("has_race_condition") is expected:
        credit += 0.5
    fix = str(submission.get("fix", "")).strip().lower()
    if fix in ACCEPTED_FIXES:
        credit += 0.5
    return credit
