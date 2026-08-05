from __future__ import annotations

from pathlib import Path

ACCEPTED_FIXES = frozenset(
    {"eager_load", "join", "prefetch", "select_related", "in_query", "batch"}
)


def _has_query_in_loop(src: str) -> bool:
    lines = src.splitlines()
    for i, line in enumerate(lines):
        if line.lstrip().startswith("for "):
            indent = len(line) - len(line.lstrip())
            for nxt in lines[i + 1:]:
                if not nxt.strip():
                    continue
                nxt_indent = len(nxt) - len(nxt.lstrip())
                if nxt_indent <= indent:
                    break
                if ".query(" in nxt or ".filter(" in nxt:
                    return True
    return False


def verify(submission: dict, fixtures: Path) -> float:
    src = (fixtures / "snippet.py").read_text(encoding="utf-8")
    expected = _has_query_in_loop(src)
    credit = 0.0
    if submission.get("has_n_plus_one") is expected:
        credit += 0.5
    fix = str(submission.get("fix", "")).strip().lower()
    if fix in ACCEPTED_FIXES:
        credit += 0.5
    return credit
