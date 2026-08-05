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

ROLE = "qa-lead"


_GATE4_DECISION = re.compile(
    r"\b(gate[- ]?4|threshold|pass(?:ed|es)?|block(?:ed|ing|er)?|"
    r"release[- ]?block(?:ing|er)?|approv(?:e|ed|al)|no[- ]?go|go[- ]?live|"
    r"sign[- ]?off|signed[- ]?off)\b",
    re.IGNORECASE,
)


def input_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    return default_input_guardrail(ctx)


def output_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    ok, feedback = default_output_guardrail(ctx)
    if not ok:
        return (ok, feedback)
    output = (ctx.output or "").strip()
    if not _GATE4_DECISION.search(output):
        return trip(
            "no gate decision: a GATE-4 eval judgment must end in an explicit "
            "decision (threshold passed / release blocked / no-go) with the "
            "evidence; the output records none — state the decision."
        )
    return ok_result()
