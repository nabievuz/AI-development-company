"""Guardrail for the ``ux-researcher`` role (design-dept — DAS-1471 family).

INPUT: reuses the shared scope screen (wrong-dept / missing-consumes /
gate-open), then adds a research-relevance screen — a ux-researcher ticket must
actually be research work, not a pure visual-design task routed to the wrong
sub-role (mirrors security-lead's terms screen). The keyword set is broad and
tolerant so a legitimate research ticket is never falsely refused.

OUTPUT: a ux-researcher deliverable is only accepted when the produced work
carries an actionable finding / recommendation. This encodes the discipline's
Definition of Done — "the analysis is delivered with sourced findings and a
clear, actionable recommendation" (role overlay). Raw notes or logistics with
no recommendation are not a delivered synthesis.
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

ROLE = "ux-researcher"

# A research ticket names at least one research concern somewhere in its scope.
_RESEARCH_TERMS = re.compile(
    r"\b(research|user|users|usability|study|interview|survey|test|testing|"
    r"insight|persona|feedback|participant|ux|journey|synthesis|behaviou?r|"
    r"qualitative|quantitative)\b",
    re.IGNORECASE,
)

# Positive evidence of an actionable finding / recommendation in the output.
# Broad and tolerant so any real synthesis carries at least one marker.
_RESEARCH_FINDING = re.compile(
    r"\b(recommend\w*|finding|findings|insight|insights|conclusion|conclude\w*|"
    r"suggest\w*|propose\w*|next\s+step|actionable|takeaway)\b",
    re.IGNORECASE,
)


def input_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    """Shared scope screen + a research-relevance screen."""
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
    """Accept only a synthesis that lands an actionable finding / recommendation."""
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
