from __future__ import annotations

import json
from pathlib import Path

_SEVERITY_RANK = {"SEV1": 0, "SEV2": 1, "SEV3": 2, "SEV4": 3}
_TIER_RANK = {"enterprise": 0, "standard": 1}


def _expected_order(incidents: list[dict]) -> list[str]:
    ordered = sorted(
        incidents,
        key=lambda inc: (
            _SEVERITY_RANK.get(inc["severity"], 99),
            _TIER_RANK.get(inc["customer_tier"], 99),
            -inc["age_minutes"],
        ),
    )
    return [inc["id"] for inc in ordered]


def verify(submission: dict, fixtures: Path) -> float:
    incidents = json.loads((fixtures / "queue.json").read_text(encoding="utf-8"))
    expected = _expected_order(incidents)
    if not expected:
        return 0.0

    seq = submission.get("order")
    if not isinstance(seq, list):
        return 0.0

    correct = sum(
        1 for i, want in enumerate(expected) if i < len(seq) and seq[i] == want
    )
    return correct / len(expected)
