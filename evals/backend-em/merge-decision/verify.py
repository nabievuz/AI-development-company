from __future__ import annotations

import json
from pathlib import Path

EXPECTED_DECISION = "request_changes"

ACCEPTED_REASONS = frozenset(
    {
        "unresolved_blocking_comment",
        "unresolved_blocking_thread",
        "missing_idempotency",
        "missing_idempotency_key",
        "unaddressed_review_feedback",
        "open_blocking_thread",
    }
)


def _document(path: Path) -> str:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return str(payload["document"])


def _normalize(value: object) -> str:
    return str(value).strip().lower().replace(" ", "_").replace("-", "_")


def verify(submission: dict, fixtures: Path) -> float:


    _ = _document(fixtures / "pr_review.json")

    credit = 0.0
    if _normalize(submission.get("decision", "")) == EXPECTED_DECISION:
        credit += 0.6
    if _normalize(submission.get("reason", "")) in ACCEPTED_REASONS:
        credit += 0.4
    return credit
