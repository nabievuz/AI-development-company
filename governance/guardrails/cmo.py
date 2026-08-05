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

ROLE = "cmo"


_DECISION_RECORDED = re.compile(
    r"\b(approved?|rejected?|decision|decided|sign[- ]?off|signed[- ]?off|"
    r"go[- ]?no[- ]?go|green[- ]?light(?:ed)?|greenlit|recommend(?:ation|ed|s)?|"
    r"adr|board[- ]?minutes|approved[- ]?queue)\b",
    re.IGNORECASE,
)


def input_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    return default_input_guardrail(ctx)


def output_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    ok, feedback = default_output_guardrail(ctx)
    if not ok:
        return (ok, feedback)
    output = (ctx.output or "").strip()
    if not _DECISION_RECORDED.search(output):
        return trip(
            "no decision recorded: a CMO deliverable must end in an explicit "
            "decision (approved / rejected / signed-off / go-no-go / a recorded "
            "ADR or board-minutes entry); the output records none — state the "
            "decision with its rationale."
        )
    return ok_result()
