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

ROLE = "board-member"


_DECISION_RECORDED = re.compile(
    r"\b("
    r"approv(?:e|ed|es|al)|reject(?:ed|s|ion)?|decid(?:e|ed|es)|decision|"
    r"ratif(?:y|ied|ies)|resolv(?:e|ed)|resolution|adopt(?:ed|s)?|endorse[ds]?|"
    r"second(?:ed)?|abstain(?:ed)?|vote[ds]?|"
    r"sign[- ]?off|signed[- ]?off|"
    r"board[- ]?minutes?|ruling|ADR|approved[- ]?queue|"
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
            "no decision recorded: a board-member review/vote must end in an "
            "explicit decision (approve / reject / vote / ratified) captured in "
            "the minutes or ADR with rationale and a law-check; the output "
            "records only discussion, not a decision."
        )
    return ok_result()
