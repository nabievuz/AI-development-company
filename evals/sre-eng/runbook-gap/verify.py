"""Deterministic verifier — sre-eng / runbook-gap."""
from __future__ import annotations

import json
from pathlib import Path


def verify(submission: dict, fixtures: Path) -> float:
    data = json.loads((fixtures / "runbook.json").read_text(encoding="utf-8"))
    missing = set(data["required"]) - set(data["present"])
    if not missing:
        return 0.0
    reported = submission.get("missing_steps")
    if not isinstance(reported, list):
        return 0.0
    got = {str(x) for x in reported}
    hits = len(got & missing)
    false_pos = len(got - missing)
    return max(0.0, (hits - false_pos) / len(missing))
