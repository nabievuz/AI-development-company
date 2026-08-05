from __future__ import annotations

from pathlib import Path

ACCEPTED = frozenset(
    {"idempotency_key", "dedup_token", "unique_request_id", "conditional_put"}
)
_MONEY_MARKERS = ("payment", "charge", "order", "checkout")


def verify(submission: dict, fixtures: Path) -> float:
    text = (fixtures / "endpoint.md").read_text(encoding="utf-8").lower()
    expected = any(m in text for m in _MONEY_MARKERS)
    credit = 0.0
    if submission.get("idempotent") is expected:
        credit += 0.5
    if str(submission.get("mechanism", "")).strip().lower() in ACCEPTED:
        credit += 0.5
    return credit
