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

ROLE = "backend-em"


_REVIEW_DECISION = re.compile(
    r"\b(approv(?:e|ed|al)|lgtm|merg(?:e|ed|ing)|"
    r"request(?:ing|ed)?[- ]?changes|changes[- ]?requested|change[- ]?request|"
    r"returned[- ]to[- ]author|reject(?:ed)?|needs[- ]?work|"
    r"sign(?:ed)?[- ]?off)\b",
    re.IGNORECASE,
)


def input_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    return default_input_guardrail(ctx)


def output_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    ok, feedback = default_output_guardrail(ctx)
    if not ok:
        return (ok, feedback)
    if not _REVIEW_DECISION.search(ctx.output or ""):
        return trip(
            "no review decision recorded: a code review must end in an explicit "
            "verdict (approved / merged, or changes-requested / returned / "
            "blocked); the output records none — state the merge-or-return "
            "decision before it can be accepted."
        )
    return ok_result()
