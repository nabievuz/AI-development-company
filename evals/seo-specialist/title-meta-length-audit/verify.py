
from __future__ import annotations

import json
from pathlib import Path

TITLE_MIN, TITLE_MAX = 30, 60
META_MIN, META_MAX = 70, 160


def _violations(fixtures: Path) -> set[str]:
    data = json.loads((fixtures / "pages.json").read_text(encoding="utf-8"))
    bad: set[str] = set()
    for page in data.get("pages", []):
        title_len = len(str(page.get("title", "")))
        meta_len = len(str(page.get("meta_description", "")))
        title_bad = not (TITLE_MIN <= title_len <= TITLE_MAX)
        meta_bad = not (META_MIN <= meta_len <= META_MAX)
        if title_bad or meta_bad:
            bad.add(str(page.get("id")))
    return bad


def verify(submission: dict, fixtures: Path) -> float:
    expected = _violations(fixtures)
    if not expected:
        return 0.0

    reported = submission.get("violations", [])
    if not isinstance(reported, list):
        return 0.0
    reported_set = {str(x) for x in reported}

    hits = len(reported_set & expected)
    false_pos = len(reported_set - expected)
    return max(0.0, (hits - false_pos) / len(expected))
