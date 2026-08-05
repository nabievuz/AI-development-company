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

ROLE = "chairman"


_RULING_RECORDED = re.compile(
    r"\b("
    r"rul(?:e|ed|es|ing)|approv(?:e|ed|es|al)|reject(?:ed|s|ion)?|"
    r"decid(?:e|ed|es)|decision|ratif(?:y|ied|ies)|resolv(?:e|ed)|resolution|"
    r"adopt(?:ed|s)?|uphold|upheld|overrul(?:e|ed|es)|"
    r"sign[- ]?off|signed[- ]?off|"
    r"board[- ]?minutes?|ADR|approved[- ]?queue|"
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
    if not _RULING_RECORDED.search(ctx.output or ""):
        return trip(
            "no ruling recorded: a Chairman ruling or board minute must record an "
            "explicit decision (ruled / ratified / approved / upheld / overruled) "
            "with binding effect in the minutes or an ADR, with rationale and a "
            "law-check; the output records only a session summary, not a ruling."
        )
    return ok_result()
