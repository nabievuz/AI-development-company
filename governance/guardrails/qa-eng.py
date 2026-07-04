"""Guardrail for the ``qa-eng`` role (R4 rollout — DAS-1471).

INPUT: the shared scope screen (wrong-dept / missing-consumes / gate-open) is
sufficient for a QA engineer; a QA ticket is any engineering-dept ticket routed
to this role.

OUTPUT: a QA change is only accepted when the produced work shows **pass/fail
eval evidence** — a test / eval / regression run with a reported result. This
encodes the QA Engineer Definition of Done ("test authoring, eval runs,
regression checks") at the guardrail layer so a QA sign-off that reports no
evaluation never passes the tripwire.
"""
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

# Positive evidence that tests / evals / regression checks were authored and run
# with a reported pass-or-fail result. Tolerant + case-insensitive: a real QA
# deliverable always names at least one of these.
_EVAL_EVIDENCE = re.compile(
    r"\b(tests?|tested|testing|pytest|eval|evals|evaluation|regression|"
    r"coverage|assert(?:ion|ions|ed)?|pass(?:ed|es)?|fail(?:ed|ing|ure|ures)?|"
    r"green)\b",
    re.IGNORECASE,
)


def input_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    """QA engineers accept any in-department, gate-clear ticket."""
    return default_input_guardrail(ctx)


def output_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    """Accept only a QA deliverable that reports pass/fail eval evidence."""
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
