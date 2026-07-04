"""Guardrail for the ``growth-marketer`` role (marketing — DAS-1471).

INPUT: the shared scope screen (wrong-dept / missing-consumes / gate-open) is
sufficient — a growth-marketer ticket is any marketing-dept campaign / growth
ticket, so no extra relevance screen is layered on.

OUTPUT: a growth deliverable is only accepted when the produced work carries a
numeric metric or target — growth work is measured, not asserted. This encodes
the discipline's Definition of Done (campaigns / growth experiments produced and
reviewed): a growth result with no number, rate, or target metric is not a
result.
"""
from __future__ import annotations

import re

from guardrails import (
    GuardrailContext,
    GuardrailResult,
    default_input_guardrail,
    default_output_guardrail,
    ok_result,
    trip,
)

ROLE = "growth-marketer"

# Positive evidence of a numeric metric / target: a percentage, a currency
# figure, a unit-suffixed number (12k / 3.5x), or a named growth metric.
_GROWTH_METRIC = re.compile(
    r"\d+\s?%|\$\s?\d|\b\d+(?:\.\d+)?\s?[kmx]\b|"
    r"\b(cac|ctr|cpa|cpc|cpm|roas|ltv|mrr|arr|conversion|retention|"
    r"sign[- ]?ups?|signups?|activation|uplift|cohort|funnel|impressions?|"
    r"clicks?|churn|kpi|metric|baseline|target|budget)\b",
    re.IGNORECASE,
)


def input_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    """The growth marketer accepts any in-department, gate-clear marketing ticket."""
    return default_input_guardrail(ctx)


def output_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    """Accept only a growth deliverable that carries a numeric metric / target."""
    ok, feedback = default_output_guardrail(ctx)
    if not ok:
        return (ok, feedback)
    output = (ctx.output or "").strip()
    if not _GROWTH_METRIC.search(output):
        return trip(
            "no metric: a growth deliverable must carry a numeric metric or "
            "target (a %, a $ figure, a named metric like CAC/CTR/conversion, or "
            "a target/baseline); the output carries none — measure the campaign "
            "or experiment and report the number."
        )
    return ok_result()
