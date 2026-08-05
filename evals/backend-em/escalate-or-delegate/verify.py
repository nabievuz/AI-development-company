from __future__ import annotations

from pathlib import Path


EXPECTED_ACTION = {1: "delegate", 2: "escalate", 3: "delegate"}

VALID_DELEGATE_TARGETS = frozenset({"backend-eng-1", "backend-eng-2"})
VALID_ESCALATE_TARGETS = frozenset({"cto"})


def _normalize(value: object) -> str:
    return str(value).strip().lower().replace(" ", "_")


def _score_one(decision: dict) -> float:
    scenario = decision.get("scenario")
    expected = EXPECTED_ACTION.get(scenario)
    if expected is None:
        return 0.0

    action = _normalize(decision.get("action", ""))
    if action != expected:
        return 0.0

    credit = 0.7
    target = _normalize(decision.get("target", ""))
    valid_targets = (
        VALID_ESCALATE_TARGETS if expected == "escalate" else VALID_DELEGATE_TARGETS
    )
    if target in valid_targets:
        credit += 0.3
    return credit


def verify(submission: dict, fixtures: Path) -> float:


    _ = (fixtures / "scenarios.md").read_text(encoding="utf-8")

    decisions = submission.get("decisions")
    if not isinstance(decisions, list) or not decisions:
        return 0.0

    by_scenario = {
        d.get("scenario"): d for d in decisions if isinstance(d, dict)
    }
    if not by_scenario:
        return 0.0

    scores = [
        _score_one(by_scenario[s]) if s in by_scenario else 0.0
        for s in EXPECTED_ACTION
    ]
    return sum(scores) / len(scores)
