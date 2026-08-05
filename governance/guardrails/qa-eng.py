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

ROLE = "qa-eng"


_EVAL_EVIDENCE = re.compile(
    r"\b(tests?|tested|testing|pytest|eval|evals|evaluation|regression|"
    r"coverage|assert(?:ion|ions|ed)?|pass(?:ed|es)?|fail(?:ed|ing|ure|ures)?|"
    r"green)\b",
    re.IGNORECASE,
)


def input_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    return default_input_guardrail(ctx)


def output_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    ok, feedback = default_output_guardrail(ctx)
    if not ok:
        return (ok, feedback)
    output = (ctx.output or "").strip()
    if not _EVAL_EVIDENCE.search(output):
        return trip(
            "no eval evidence: a QA deliverable must report a test / eval / "
            "regression run with a pass-or-fail result; the output records none "
            "— run the checks and report the outcome before it can be accepted."
        )
    return ok_result()
