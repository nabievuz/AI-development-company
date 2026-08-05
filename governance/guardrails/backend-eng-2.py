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

ROLE = "backend-eng-2"


_TEST_EVIDENCE = re.compile(
    r"\b(test|tests|pytest|passed|passing|green|coverage|assert|ci)\b",
    re.IGNORECASE,
)


_RED_BUILD = re.compile(
    r"(?i)\b("
    r"ci (?:is )?red|build (?:is )?(?:failing|broken|red)|"
    r"tests? (?:are |is )?(?:failing|red)|suite (?:is )?(?:red|failing)|"
    r"still (?:failing|broken|red)|no tests"
    r")\b",
)


def input_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    return default_input_guardrail(ctx)


def output_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    ok, feedback = default_output_guardrail(ctx)
    if not ok:
        return (ok, feedback)
    output = ctx.output or ""
    if _RED_BUILD.search(output):
        return trip(
            "red build: the output asserts a CURRENT failing/red state "
            "(e.g. 'CI is red' / 'tests are failing' / 'no tests'); fix it to "
            "green before it can be accepted (LAW 5 — green CI = done)."
        )
    if not _TEST_EVIDENCE.search(output):
        return trip(
            "no test evidence: a backend change must ship with tests and a green "
            "run; the output shows none — add tests and report the passing run."
        )
    return ok_result()
