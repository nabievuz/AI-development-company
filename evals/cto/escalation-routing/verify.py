"""Deterministic verifier — cto / escalation-routing.

Recomputes the expected (action, route) pair for each scenario in
``fixtures/scenarios.json`` from the escalation policy stated in ``task.md``
(budget ceiling, cross-dept conflict, explicit CEO-approval flag; otherwise
delegate to the domain-owning lead). The expected answer is derived from the
SAME fixture the agent was given — doing the escalation judgment correctly
reproduces it — so nothing is leaked: the fixture is the input, and applying
the policy is the graded skill. Deterministic (no clock/model). An empty
submission scores 0.0.
"""

from __future__ import annotations

import json
from pathlib import Path

_DOMAIN_ROUTE = {
    "backend": "backend-em",
    "frontend": "frontend-em",
    "quality": "qa-lead",
    "security": "security-lead",
    "infra": "sre-lead",
}

_BUDGET_CEILING = 250_000


def _expected(fixtures: Path) -> dict[str, tuple[str, str]]:
    data = json.loads((fixtures / "scenarios.json").read_text(encoding="utf-8"))
    expected: dict[str, tuple[str, str]] = {}
    for scenario in data:
        sid = str(scenario["id"])
        must_escalate = (
            scenario.get("budget_usd", 0) > _BUDGET_CEILING
            or bool(scenario.get("cross_dept_conflict", False))
            or bool(scenario.get("requires_ceo_approval", False))
        )
        if must_escalate:
            expected[sid] = ("escalate", "ceo")
        else:
            domain = scenario.get("domain")
            expected[sid] = ("delegate", _DOMAIN_ROUTE.get(domain, "__unknown__"))
    return expected


def verify(submission: dict, fixtures: Path) -> float:
    """Return fractional credit in [0.0, 1.0] for one submission."""
    expected = _expected(fixtures)
    if not expected:
        return 0.0

    decisions = submission.get("decisions", {})
    if not isinstance(decisions, dict):
        return 0.0

    correct = 0
    for sid, (exp_action, exp_route) in expected.items():
        entry = decisions.get(sid)
        if not isinstance(entry, dict):
            continue
        if entry.get("action") == exp_action and entry.get("route") == exp_route:
            correct += 1
    return correct / len(expected)
