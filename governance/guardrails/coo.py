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

ROLE = "coo"


_DECISION = re.compile(
    r"\b(decision|decided|decide|approv(?:e|ed|al)|reject(?:ed|s)?|"
    r"adr|go[- ]?ahead|no[- ]?go|greenlit|greenlight|ratif(?:y|ied)|"
    r"plan[- ]of[- ]record|sign[- ]?off|signed[- ]?off|authoriz(?:e|ed))\b",
    re.IGNORECASE,
)


def input_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    return default_input_guardrail(ctx)


def output_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    ok, feedback = default_output_guardrail(ctx)
    if not ok:
        return (ok, feedback)
    output = (ctx.output or "").strip()
    if not _DECISION.search(output):
        return trip(
            "no decision recorded: a COO deliverable must end in an explicit "
            "decision or approval (decided / approved / go / no-go / signed-off) "
            "with the rationale captured; the output records none — make the call "
            "and record it (ADR / board minutes / approved queue)."
        )
    return ok_result()
