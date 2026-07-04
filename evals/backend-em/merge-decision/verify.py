"""Deterministic verifier — backend-em / merge-decision."""
from __future__ import annotations

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


def _normalize(value: object) -> str:
    return str(value).strip().lower().replace(" ", "_").replace("-", "_")


def verify(submission: dict, fixtures: Path) -> float:
    # fixtures/pr_review.md is read for parity with other verifiers (and to
    # keep this deterministic against the recorded scenario) even though the
    # expected answer is fixed for this task instance.
    _ = (fixtures / "pr_review.md").read_text(encoding="utf-8")

    credit = 0.0
    if _normalize(submission.get("decision", "")) == EXPECTED_DECISION:
        credit += 0.6
    if _normalize(submission.get("reason", "")) in ACCEPTED_REASONS:
        credit += 0.4
    return credit
