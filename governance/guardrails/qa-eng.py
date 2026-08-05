from __future__ import annotations

from guardrails import (
    GuardrailContext,
    GuardrailResult,
    default_input_guardrail,
    default_output_guardrail,
)
from guardrails.honesty import screen_reported_run

ROLE = "qa-eng"


MISSING_EVIDENCE = (
    "no eval evidence: a QA deliverable must report a test / eval / regression "
    "run with a concrete result — the command or suite that ran and its "
    "counts; the output records none. Reporting failures is a legitimate QA "
    "deliverable and is never penalised here — reporting nothing is."
)


def input_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    return default_input_guardrail(ctx)


def output_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    ok, feedback = default_output_guardrail(ctx)
    if not ok:
        return (ok, feedback)
    return screen_reported_run(ctx.output or "", missing_evidence_reason=MISSING_EVIDENCE)
