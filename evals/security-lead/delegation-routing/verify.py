
from __future__ import annotations

import json
from pathlib import Path

_COST_CEILING = 100_000


def _expected(fixtures: Path) -> dict[str, tuple[str, str]]:
    data = json.loads((fixtures / "requests.json").read_text(encoding="utf-8"))
    expected: dict[str, tuple[str, str]] = {}
    for req in data:
        rid = str(req["id"])
        must_escalate = (
            req.get("blast_radius") == "org-wide"
            or bool(req.get("requires_policy_exception", False))
            or req.get("estimated_remediation_cost_usd", 0) > _COST_CEILING
        )
        if must_escalate:
            expected[rid] = ("escalate", "cto")
        else:
            expected[rid] = ("delegate", "security-eng")
    return expected


def verify(submission: dict, fixtures: Path) -> float:
    expected = _expected(fixtures)
    if not expected:
        return 0.0

    decisions = submission.get("decisions", {})
    if not isinstance(decisions, dict):
        return 0.0

    correct = 0
    for rid, (exp_action, exp_route) in expected.items():
        entry = decisions.get(rid)
        if not isinstance(entry, dict):
            continue
        if entry.get("action") == exp_action and entry.get("route") == exp_route:
            correct += 1
    return correct / len(expected)
