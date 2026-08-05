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

ROLE = "sre-lead"


_GATE5_DECISION = re.compile(
    r"\b(gate[- ]?5|sign[- ]?off|signed[- ]?off|approv(?:e|ed|al)|"
    r"block(?:ed|ing|er)?|go[- ]?live|no[- ]?go|launch(?:ed)?|roll[- ]?back|"
    r"deploy(?:ment)?[- ]?approved|observability)\b",
    re.IGNORECASE,
)


def input_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    return default_input_guardrail(ctx)


def output_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    ok, feedback = default_output_guardrail(ctx)
    if not ok:
        return (ok, feedback)
    output = (ctx.output or "").strip()
    if not _GATE5_DECISION.search(output):
        return trip(
            "no launch decision: a GATE-5 production-launch judgment must end in "
            "an explicit decision (go-live / sign-off / approved, or blocked / "
            "no-go) with the observability evidence; the output records none — "
            "state the decision."
        )
    return ok_result()
