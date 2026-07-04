"""Deterministic verifier — frontend-eng-1 / ui-state-bug-classification."""
from __future__ import annotations

import json
from pathlib import Path

# id -> accepted synonyms for the correct category.
_ACCEPTED = {
    "s1": {"missing-cleanup", "no-cleanup", "uncleared-interval", "missing-teardown"},
    "s2": {"stale-closure", "stale-state", "missing-dependency", "stale-value"},
    "s3": {"race-condition", "race", "stale-response", "out-of-order-response"},
    "s4": {"ok", "no-bug", "none", "correct", "no-issue"},
    "s5": {"ok", "no-bug", "none", "correct", "no-issue"},
}


def verify(submission: dict, fixtures: Path) -> float:
    snippets = json.loads(
        (fixtures / "snippets.json").read_text(encoding="utf-8")
    )["snippets"]

    classifications = submission.get("classifications")
    if not isinstance(classifications, dict) or not snippets:
        return 0.0

    correct = 0
    for snippet in snippets:
        sid = snippet["id"]
        got = classifications.get(sid)
        if isinstance(got, str) and got.strip().lower() in _ACCEPTED.get(sid, set()):
            correct += 1
    return correct / len(snippets)
