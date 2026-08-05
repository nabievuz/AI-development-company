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

ROLE = "senior-pm"


_PRD_ARTIFACT = re.compile(
    r"\b(prd|spec|specs|specification|requirement\w*|acceptance[- ]criteri\w*|"
    r"user stor(?:y|ies)|success metric\w*)\b"
    r"|\bADR-\d+\b|/specs?/",
    re.IGNORECASE,
)


def input_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    return default_input_guardrail(ctx)


def output_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    ok, feedback = default_output_guardrail(ctx)
    if not ok:
        return (ok, feedback)
    output = ctx.output or ""
    if not _PRD_ARTIFACT.search(output):
        return trip(
            "no spec artifact: a senior-PM deliverable must produce a concrete "
            "PRD / spec / requirements artifact (requirements, acceptance "
            "criteria, user stories, success metrics, specs/…); the output "
            "records none — write the spec before it can be accepted (GATE-1)."
        )
    return ok_result()
