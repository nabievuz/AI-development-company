"""Deterministic verifier — finance-analyst / unit-economics.

Grades LTV and LTV:CAC ratio against values derived from the same fixture the
agent was given, each with a tolerance band (full credit within 2% relative
error, decaying to 0 by 22% relative error). Deterministic (no clock/model).
An empty submission scores 0.0.
"""

from __future__ import annotations

import json
from pathlib import Path

FULL_CREDIT_TOL = 0.02   # relative error below this earns 1.0
DECAY_BAND = 0.20        # credit decays linearly across this extra band to 0.0


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _expected(fixtures: Path) -> tuple[float, float]:
    data = json.loads((fixtures / "metrics.json").read_text(encoding="utf-8"))
    arpu = float(data["arpu_monthly_usd"])
    margin = float(data["gross_margin_pct"]) / 100.0
    churn = float(data["monthly_churn_pct"]) / 100.0
    cac = float(data["cac_usd"])

    ltv = arpu * margin / churn
    ratio = ltv / cac
    return ltv, ratio


def _field_credit(value: object, expected: float) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return 0.0
    if expected == 0:
        return 1.0 if abs(value) < 1e-9 else 0.0
    rel_err = abs(value - expected) / abs(expected)
    if rel_err <= FULL_CREDIT_TOL:
        return 1.0
    return clamp01(1.0 - (rel_err - FULL_CREDIT_TOL) / DECAY_BAND)


def verify(submission: dict, fixtures: Path) -> float:
    """Return fractional credit in [0.0, 1.0] for one submission."""
    expected_ltv, expected_ratio = _expected(fixtures)

    ltv_credit = _field_credit(submission.get("ltv"), expected_ltv)
    ratio_credit = _field_credit(submission.get("ltv_cac_ratio"), expected_ratio)

    return (ltv_credit + ratio_credit) / 2.0
