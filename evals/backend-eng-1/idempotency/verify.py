from __future__ import annotations

import json
from pathlib import Path

ACCEPTED = frozenset(
    {"idempotency_key", "dedup_token", "unique_request_id", "conditional_put"}
)
_MONEY_MARKERS = ("payment", "charge", "order", "checkout")


def _document(path: Path) -> str:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return str(payload["document"])


def verify(submission: dict, fixtures: Path) -> float:
    text = _document(fixtures / "endpoint.json").lower()
    expected = any(m in text for m in _MONEY_MARKERS)
    credit = 0.0
    if submission.get("idempotent") is expected:
        credit += 0.5
    if str(submission.get("mechanism", "")).strip().lower() in ACCEPTED:
        credit += 0.5
    return credit
