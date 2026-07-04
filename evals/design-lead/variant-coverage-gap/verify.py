"""Deterministic verifier — design-lead / variant-coverage-gap.

Fractional credit rewards true positives and penalises false positives:

    credit = clamp01( (|reported ∩ undefined| - |reported \\ undefined|) / |undefined| )

The undefined set is derived by diffing the SAME design-system registry and
screen-usage list the agent was given — doing the governance check correctly
reproduces it, so nothing is leaked: the fixtures are the input, the graded
answer key lives only here. Deterministic (no clock/model). An empty
submission scores 0.0.
"""
from __future__ import annotations

import json
from pathlib import Path


def _undefined_usages(fixtures: Path) -> set[str]:
    system = json.loads((fixtures / "design-system.json").read_text(encoding="utf-8"))
    usage = json.loads((fixtures / "screen-usage.json").read_text(encoding="utf-8"))
    components: dict[str, list[str]] = system.get("components", {})

    undefined: set[str] = set()
    for item in usage.get("usages", []):
        component = str(item["component"])
        variant = str(item["variant"])
        defined_variants = components.get(component)
        if defined_variants is None or variant not in defined_variants:
            undefined.add(f"{component}:{variant}")
    return undefined


def verify(submission: dict, fixtures: Path) -> float:
    expected = _undefined_usages(fixtures)
    if not expected:
        return 0.0

    reported = submission.get("undefined", [])
    if not isinstance(reported, list):
        return 0.0
    reported_set = {str(x) for x in reported}

    hits = len(reported_set & expected)
    false_pos = len(reported_set - expected)
    return max(0.0, (hits - false_pos) / len(expected))
