from __future__ import annotations

from guardrails import (
    GuardrailContext,
    GuardrailResult,
    default_input_guardrail,
    default_output_guardrail,
)
from guardrails.honesty import screen_verified_change

ROLE = "frontend-eng-1"


MISSING_EVIDENCE = (
    "no CI evidence: a frontend change must ship as a reviewed PR with a "
    "reported check run — name what you ran (jest / vitest / playwright / "
    "lint / typecheck / build / CI) and give its outcome with counts; the "
    "output cites none (LAW 5 — green CI = done)."
)


def input_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    return default_input_guardrail(ctx)


def output_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    ok, feedback = default_output_guardrail(ctx)
    if not ok:
        return (ok, feedback)
    return screen_verified_change(ctx.output or "", missing_evidence_reason=MISSING_EVIDENCE)
