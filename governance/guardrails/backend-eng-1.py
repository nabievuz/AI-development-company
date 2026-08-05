from __future__ import annotations

from guardrails import (
    GuardrailContext,
    GuardrailResult,
    default_input_guardrail,
    default_output_guardrail,
)
from guardrails.honesty import screen_verified_change

ROLE = "backend-eng-1"


MISSING_EVIDENCE = (
    "no test evidence: a backend change must ship with tests and a reported "
    "run — name the command (pytest / the full suite / CI) and give its result "
    "with counts, or state the regression test that failed before the fix and "
    "passes with it; the output shows none."
)


def input_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    return default_input_guardrail(ctx)


def output_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    ok, feedback = default_output_guardrail(ctx)
    if not ok:
        return (ok, feedback)
    return screen_verified_change(ctx.output or "", missing_evidence_reason=MISSING_EVIDENCE)
