
from __future__ import annotations

import json
from pathlib import Path


def _theme_coverage(fixtures: Path) -> tuple[str, int]:
    data = json.loads((fixtures / "sessions.json").read_text(encoding="utf-8"))
    sessions = data.get("sessions", [])

    coverage: dict[str, set[str]] = {}
    order: list[str] = []
    for session in sessions:
        sid = session.get("session_id")
        for obs in session.get("observations", []):
            theme = obs.get("theme")
            if theme not in coverage:
                coverage[theme] = set()
                order.append(theme)
            coverage[theme].add(sid)

    best_theme = ""
    best_count = -1
    for theme in order:
        count = len(coverage[theme])
        if count > best_count:
            best_theme = theme
            best_count = count
    return best_theme, best_count


def verify(submission: dict, fixtures: Path) -> float:
    top_theme, session_count = _theme_coverage(fixtures)
    if not top_theme:
        return 0.0

    credit = 0.0

    got_theme = submission.get("top_theme")
    if isinstance(got_theme, str) and got_theme.strip() == top_theme:
        credit += 0.5

    got_count = submission.get("session_count")
    if (
        isinstance(got_count, int)
        and not isinstance(got_count, bool)
        and got_count == session_count
    ):
        credit += 0.5

    return credit
