"""Deterministic verifier — board-member / hire-vote-tally."""
from __future__ import annotations

import json
from pathlib import Path


def _expected(fixtures: Path) -> dict[str, str]:
    data = json.loads((fixtures / "hires.json").read_text(encoding="utf-8"))
    board_roles = set(data["board_roles"])
    out: dict[str, str] = {}
    for req in data["requests"]:
        counting = [v for v in req["votes"] if v.get("role") in board_roles]
        has_reject = any(v.get("vote") == "reject" for v in counting)
        has_approve = any(v.get("vote") == "approve" for v in counting)
        if has_reject:
            out[req["id"]] = "rejected"
        elif has_approve:
            out[req["id"]] = "approved"
        else:
            out[req["id"]] = "pending"
    return out


def verify(submission: dict, fixtures: Path) -> float:
    expected = _expected(fixtures)
    decisions = submission.get("decisions")
    if not isinstance(decisions, dict) or not decisions:
        return 0.0
    correct = 0
    for req_id, want in expected.items():
        got = decisions.get(req_id)
        if isinstance(got, str) and got.strip().lower() == want:
            correct += 1
    return correct / len(expected)
