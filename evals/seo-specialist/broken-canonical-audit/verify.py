
from __future__ import annotations

import json
from pathlib import Path


def _broken(fixtures: Path) -> set[str]:
    data = json.loads((fixtures / "pages.json").read_text(encoding="utf-8"))
    pages = data.get("pages", [])
    known_urls = {str(p.get("url")) for p in pages}

    broken: set[str] = set()
    for page in pages:
        url = str(page.get("url"))
        canonical = str(page.get("canonical", "")).strip()
        if not canonical:
            broken.add(url)
            continue
        if canonical != url and canonical not in known_urls:
            broken.add(url)
    return broken


def verify(submission: dict, fixtures: Path) -> float:
    expected = _broken(fixtures)
    if not expected:
        return 0.0

    reported = submission.get("broken_urls", [])
    if not isinstance(reported, list):
        return 0.0
    reported_set = {str(x) for x in reported}

    hits = len(reported_set & expected)
    false_pos = len(reported_set - expected)
    return max(0.0, (hits - false_pos) / len(expected))
