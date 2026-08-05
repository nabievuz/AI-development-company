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

ROLE = "cpo"


_DECISION = re.compile(
    r"\b(decid\w*|decision|approv\w*|reject\w*|prioriti[sz]\w*|roadmap|"
    r"ratif\w*|green[- ]?light|sign[- ]?off|signed[- ]?off|greenlit)\b"
    r"|\bADR-\d+\b",
    re.IGNORECASE,
)


def input_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    return default_input_guardrail(ctx)


def output_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    ok, feedback = default_output_guardrail(ctx)
    if not ok:
        return (ok, feedback)
    output = ctx.output or ""
    if not _DECISION.search(output):
        return trip(
            "no decision recorded: a CPO deliverable must end in an explicit "
            "decision (decided / approved / rejected / prioritized / roadmap / "
            "ADR-NNNN) with the rationale; the output records none — make and "
            "record the call before it can be accepted."
        )
    return ok_result()
