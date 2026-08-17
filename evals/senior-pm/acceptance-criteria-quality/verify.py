from __future__ import annotations

from pathlib import Path

_SCENARIOS: list[dict] = [
    {"id": "expired_link", "keywords": ["expired"]},
    {"id": "rate_limited", "keywords": ["rate", "limit"]},
    {"id": "invalid_input", "keywords": ["invalid", "email"]},
    {"id": "reused_token", "keywords": ["already", "used"]},
]

_GWT_MARKERS = ("given", "when", "then")


def _covers(text: str, keywords: list[str]) -> bool:
    lowered = text.lower()
    return all(kw.lower() in lowered for kw in keywords)


def _is_gwt(text: str) -> bool:
    lowered = text.lower()
    return sum(marker in lowered for marker in _GWT_MARKERS) >= 2


def verify(submission: dict, fixtures: Path) -> float:
    criteria = submission.get("acceptance_criteria")
    if not isinstance(criteria, list) or not criteria:
        return 0.0
    strings = [str(c) for c in criteria if isinstance(c, str | int | float)]
    if not strings:
        return 0.0

    total_scenarios = len(_SCENARIOS)
    covered = 0
    for scenario in _SCENARIOS:
        if any(_covers(s, scenario["keywords"]) for s in strings):
            covered += 1
    excess = max(0, len(strings) - 2 * total_scenarios)
    scenario_coverage = max(0.0, (covered - excess) / total_scenarios)

    gwt_count = sum(1 for s in strings if _is_gwt(s))
    structure_fraction = gwt_count / len(strings)

    credit = 0.7 * scenario_coverage + 0.3 * structure_fraction
    return max(0.0, min(1.0, credit))
