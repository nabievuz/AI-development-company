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

ROLE = "ux-researcher"


_RESEARCH_TERMS = re.compile(
    r"\b(research|user|users|usability|study|interview|survey|test|testing|"
    r"insight|persona|feedback|participant|ux|journey|synthesis|behaviou?r|"
    r"qualitative|quantitative)\b",
    re.IGNORECASE,
)


_RESEARCH_FINDING = re.compile(
    r"\b(recommend\w*|finding|findings|insight|insights|conclusion|conclude\w*|"
    r"suggest\w*|propose\w*|next\s+step|actionable|takeaway)\b",
    re.IGNORECASE,
)


def input_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    ok, feedback = default_input_guardrail(ctx)
    if not ok:
        return (ok, feedback)
    haystack = f"{ctx.frontmatter.get('title', '')}\n{ctx.body}"
    if not _RESEARCH_TERMS.search(haystack):
        return trip(
            "off-scope for ux-researcher: the ticket names no research concern "
            "(user / usability / study / interview / survey / insight / …); "
            "re-route to the owning design role."
        )
    return ok_result()


def output_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    ok, feedback = default_output_guardrail(ctx)
    if not ok:
        return (ok, feedback)
    output = ctx.output or ""
    if not _RESEARCH_FINDING.search(output):
        return trip(
            "no actionable finding: a ux-researcher deliverable must land a "
            "sourced finding and a clear, actionable recommendation "
            "(finding / insight / recommendation / next step); the output has "
            "none — synthesize the raw notes into a recommendation."
        )
    return ok_result()
