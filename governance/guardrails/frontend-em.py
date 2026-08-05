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

ROLE = "frontend-em"


_REVIEW_DECISION = re.compile(
    r"(?i)(?:"
    r"\bapprov\w*\b|"
    r"\bmerg(?:e|ed|ing)\b|"
    r"\blgtm\b|"
    r"\bgate-?\s?3\b|"
    r"\breject\w*\b|"
    r"\bblocked\b|"
    r"\breturned\b|"
    r"request\w*\s+chang\w*|"
    r"chang\w*\s+request\w*"
    r")"
)


def input_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    return default_input_guardrail(ctx)


def output_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    ok, feedback = default_output_guardrail(ctx)
    if not ok:
        return (ok, feedback)
    if not _REVIEW_DECISION.search(ctx.output or ""):
        return trip(
            "no review decision recorded: a Frontend EM review must end in an "
            "explicit decision — approved/merged (GATE-3, green CI) or returned "
            "with concrete change requests; the output records neither."
        )
    return ok_result()
