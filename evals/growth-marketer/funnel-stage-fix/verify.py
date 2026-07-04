"""Deterministic verifier — growth-marketer / funnel-stage-fix."""
from __future__ import annotations

import json
from pathlib import Path

_LIFT_TOLERANCE = 5


def _analyse(fixtures: Path) -> tuple[str, float]:
    funnel = json.loads((fixtures / "funnel.json").read_text(encoding="utf-8"))["funnel"]
    worst_stage = None
    worst_gap = -1.0
    worst_lift = 0.0
    for prev, cur in zip(funnel, funnel[1:]):
        prev_visitors = prev["visitors"]
        if prev_visitors <= 0:
            continue
        actual_rate = cur["visitors"] / prev_visitors
        benchmark_rate = cur["benchmark_rate"]
        gap = benchmark_rate - actual_rate
        if gap > worst_gap:
            worst_gap = gap
            worst_stage = cur["stage"]
            worst_lift = round(prev_visitors * benchmark_rate - cur["visitors"])
    return str(worst_stage), float(worst_lift)


def verify(submission: dict, fixtures: Path) -> float:
    expected_stage, expected_lift = _analyse(fixtures)
    credit = 0.0
    if str(submission.get("priority_stage", "")).strip() == expected_stage:
        credit += 0.5
    lift = submission.get("expected_lift")
    if isinstance(lift, (int, float)) and abs(float(lift) - expected_lift) <= _LIFT_TOLERANCE:
        credit += 0.5
    return credit
