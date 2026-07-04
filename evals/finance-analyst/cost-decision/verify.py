"""Deterministic verifier — finance-analyst / cost-decision.

Grades a build-vs-buy call: half credit for picking the cheaper option over
the horizon, half credit (linearly decaying over a 6-month window) for the
breakeven month. Both expected values are derived from the same fixture the
agent was given. Deterministic (no clock/model). An empty submission scores
0.0.
"""

from __future__ import annotations

import json
from pathlib import Path

MONTH_DECAY_WINDOW = 6  # month-difference beyond which breakeven credit is 0


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _cumulative_costs(fixtures: Path) -> tuple[str, int | None, int]:
    data = json.loads((fixtures / "vendor_options.json").read_text(encoding="utf-8"))
    upfront = float(data["build"]["upfront_cost_usd"])
    maintenance = float(data["build"]["monthly_maintenance_usd"])
    subscription = float(data["buy"]["monthly_subscription_usd"])
    horizon = int(data["horizon_months"])

    breakeven_month: int | None = None
    for m in range(1, horizon + 1):
        build_cost = upfront + maintenance * m
        buy_cost = subscription * m
        if build_cost <= buy_cost:
            breakeven_month = m
            break

    build_total = upfront + maintenance * horizon
    buy_total = subscription * horizon
    cheaper = "build" if build_total <= buy_total else "buy"
    return cheaper, breakeven_month, horizon


def verify(submission: dict, fixtures: Path) -> float:
    """Return fractional credit in [0.0, 1.0] for one submission."""
    expected_cheaper, expected_month, horizon = _cumulative_costs(fixtures)

    option_credit = 1.0 if submission.get("cheaper_option") == expected_cheaper else 0.0

    reported_month = submission.get("breakeven_month")
    if isinstance(reported_month, bool) or not isinstance(reported_month, int):
        month_credit = 0.0
    elif expected_month is None:
        month_credit = 1.0 if reported_month is None else 0.0
    else:
        diff = abs(reported_month - expected_month)
        month_credit = clamp01(1.0 - diff / MONTH_DECAY_WINDOW)

    return 0.5 * option_credit + 0.5 * month_credit
