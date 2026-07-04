"""Deterministic verifier — sre-eng / alert-threshold."""
from __future__ import annotations

import json
from pathlib import Path


def verify(submission: dict, fixtures: Path) -> float:
    slo = json.loads((fixtures / "slo.json").read_text(encoding="utf-8"))
    budget_pct = 100.0 - float(slo["availability_target_pct"])
    downtime = slo["window_days"] * 24 * 60 * budget_pct / 100.0
    credit = 0.0
    got_budget = submission.get("error_budget_pct")
    if isinstance(got_budget, (int, float)) and not isinstance(got_budget, bool):
        if abs(float(got_budget) - budget_pct) <= 1e-6:
            credit += 0.5
    got_dt = submission.get("downtime_minutes")
    if isinstance(got_dt, (int, float)) and not isinstance(got_dt, bool):
        if abs(float(got_dt) - downtime) <= 1e-3:
            credit += 0.5
    return credit
