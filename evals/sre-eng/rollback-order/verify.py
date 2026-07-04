"""Deterministic verifier — sre-eng / rollback-order."""
from __future__ import annotations

import json
from pathlib import Path


def verify(submission: dict, fixtures: Path) -> float:
    steps = json.loads((fixtures / "deploy.json").read_text(encoding="utf-8"))["steps"]
    expected = list(reversed(steps))
    seq = submission.get("rollback_sequence")
    if not isinstance(seq, list) or not expected:
        return 0.0
    correct = sum(
        1 for i, want in enumerate(expected) if i < len(seq) and seq[i] == want
    )
    return correct / len(expected)
