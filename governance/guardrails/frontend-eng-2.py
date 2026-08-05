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

ROLE = "frontend-eng-2"


_CI_EVIDENCE = re.compile(
    r"\b(test|tests|jest|vitest|cypress|playwright|e2e|lint|build|ci|green|"
    r"pass|passed|passing|coverage|snapshot|storybook|typecheck|tsc)\b",
    re.IGNORECASE,
)


def input_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    return default_input_guardrail(ctx)


def output_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    ok, feedback = default_output_guardrail(ctx)
    if not ok:
        return (ok, feedback)
    if not _CI_EVIDENCE.search(ctx.output or ""):
        return trip(
            "no CI evidence: a frontend change must ship as a reviewed PR with "
            "green CI (tests / lint / build passing); the output cites none — "
            "run the checks and report the passing run (LAW 5 — green CI = done)."
        )
    return ok_result()
