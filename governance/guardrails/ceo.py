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

ROLE = "ceo"


_DECISION_RECORDED = re.compile(
    r"\b("
    r"approv(?:e|ed|es|al)|reject(?:ed|s|ion)?|decid(?:e|ed|es)|decision|"
    r"ratif(?:y|ied|ies)|resolv(?:e|ed)|resolution|adopt(?:ed|s)?|endorse[ds]?|"
    r"arbitrat(?:e|ed|ion)|directive|mandate[ds]?|"
    r"sign[- ]?off|signed[- ]?off|approved[- ]?queue|"
    r"board[- ]?minutes?|ADR|"
    r"TASDIQLANDI"
    r")\b",
    re.IGNORECASE,
)


def input_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    return default_input_guardrail(ctx)


def output_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    ok, feedback = default_output_guardrail(ctx)
    if not ok:
        return (ok, feedback)
    if not _DECISION_RECORDED.search(ctx.output or ""):
        return trip(
            "no decision recorded: a CEO strategy call or arbitration must end "
            "in an explicit decision (approved / decided / arbitrated / ratified) "
            "captured in an ADR, board minutes, or the approved queue with "
            "rationale and a law-check; the output records only options, not a "
            "decision."
        )
    return ok_result()
