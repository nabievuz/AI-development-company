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


_GROWTH_METRIC = re.compile(
    r"\d+\s?%|\$\s?\d|\b\d+(?:\.\d+)?\s?[kmx]\b|"
    r"\b(cac|ctr|cpa|cpc|cpm|roas|ltv|mrr|arr|conversion|retention|"
    r"sign[- ]?ups?|signups?|activation|uplift|cohort|funnel|impressions?|"
    r"clicks?|churn|kpi|metric|baseline|target|budget)\b",
    re.IGNORECASE,
)


def input_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    return default_input_guardrail(ctx)


def output_guardrail(ctx: GuardrailContext) -> GuardrailResult:
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
