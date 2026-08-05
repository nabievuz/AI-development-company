from __future__ import annotations

import re

from guardrails import (
    GuardrailContext,
    GuardrailResult,
    default_input_guardrail,
    ok_result,
    trip,
)

ROLE = "backend-eng-1"


_TEST_EVIDENCE = re.compile(
    r"\b(test|tests|pytest|passed|green|coverage|assert)\b", re.IGNORECASE
)


_RED_BUILD = re.compile(
    r"\b(failed|failing|red|broken|error|traceback|no tests)\b", re.IGNORECASE
)


def input_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    return default_input_guardrail(ctx)


def output_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    output = (ctx.output or "").strip()
    if not output:
        return trip("empty output: no backend change was produced; re-run the ticket.")
    if _RED_BUILD.search(output):
        return trip(
            "red build: the output self-reports a failing / broken state "
            "(failed/red/traceback/no tests); fix it to green before it can be "
            "accepted (LAW 5 — green CI = done)."
        )
    if not _TEST_EVIDENCE.search(output):
        return trip(
            "no test evidence: a backend change must ship with tests and a green "
            "run; the output shows none — add tests and report the passing run."
        )
    return ok_result()
