"""Deterministic verifier — cto / architecture-tradeoff.

Recomputes the winning option per case in ``fixtures/cases.json`` from the
trade-off rule stated in ``task.md`` (security is a hard gate unless every
option is high-risk; then minimize cost, then latency, then id). The expected
answer is derived from the SAME fixture the agent was given — applying the
rule correctly reproduces it, so nothing is leaked. Deterministic (no
clock/model). An empty submission scores 0.0.
"""

from __future__ import annotations

import json
from pathlib import Path


def _winner(options: list[dict]) -> str:
    non_high = [o for o in options if o.get("security_risk") != "high"]
    pool = non_high if non_high else options
    best = min(
        pool,
        key=lambda o: (o.get("monthly_cost_usd", float("inf")), o.get("latency_ms", float("inf")), str(o.get("id"))),
    )
    return str(best.get("id"))


def _expected(fixtures: Path) -> dict[str, str]:
    data = json.loads((fixtures / "cases.json").read_text(encoding="utf-8"))
    return {str(case["id"]): _winner(case.get("options", [])) for case in data}


def verify(submission: dict, fixtures: Path) -> float:
    """Return fractional credit in [0.0, 1.0] for one submission."""
    expected = _expected(fixtures)
    if not expected:
        return 0.0

    choices = submission.get("choices", {})
    if not isinstance(choices, dict):
        return 0.0

    correct = sum(
        1 for cid, winner in expected.items() if str(choices.get(cid)) == winner
    )
    return correct / len(expected)
