"""Deterministic verifier — sre-lead / rollback-go-nogo."""
from __future__ import annotations

import json
from pathlib import Path


def _expected_decision(dep: dict) -> str:
    if bool(dep["data_loss_risk"]):
        return "ROLLBACK"
    if bool(dep["migration_irreversible"]):
        return "FORWARD_FIX"
    if dep["error_rate_increase_pct"] >= 5 or dep["p99_latency_increase_pct"] >= 100:
        return "ROLLBACK"
    return "MONITOR"


def verify(submission: dict, fixtures: Path) -> float:
    deployments = json.loads(
        (fixtures / "deployments.json").read_text(encoding="utf-8")
    )
    if not deployments:
        return 0.0

    reported = submission.get("decisions")
    if not isinstance(reported, dict):
        return 0.0

    hits = 0
    for dep in deployments:
        expected = _expected_decision(dep)
        if reported.get(dep["id"]) == expected:
            hits += 1
    return hits / len(deployments)
