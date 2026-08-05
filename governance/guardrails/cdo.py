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

ROLE = "cdo"


_DECISION = re.compile(
    r"\b(decision|decided|decide|approv\w*|reject\w*|ratif\w*|endorse\w*|"
    r"greenlit|green[- ]?light|go[- ]?ahead|direction\s+set|sign[- ]?off|"
    r"signed[- ]?off|adr)\b",
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
            "no decision recorded: a CDO deliverable must land an explicit "
            "decision / approval (decided / approved / rejected / ratified / ADR) "
            "with its rationale and law-check; the output records none — make the "
            "call and record it."
        )
    return ok_result()
