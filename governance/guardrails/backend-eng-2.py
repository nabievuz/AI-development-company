"""Guardrail for the ``backend-eng-2`` role (R4 rollout 2->32).

INPUT: the shared scope screen (wrong-dept / missing-consumes / gate-open) is
sufficient for an engineer; a backend ticket is any engineering-dept ticket.

OUTPUT: a backend change is only accepted when the produced work shows test
evidence and does not self-report a red / failing build. This encodes the
engineer's Definition of Done ("delivered as a reviewed PR with green CI, every
acceptance criterion checked") — LAW 5, "green CI = done" — at the guardrail
layer so an untested or broken change never passes the tripwire.
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

ROLE = "backend-eng-2"

# Positive evidence that tests were written / run and CI is green.
_TEST_EVIDENCE = re.compile(
    r"\b(test|tests|pytest|passed|passing|green|coverage|assert|ci)\b",
    re.IGNORECASE,
)

# A CURRENT failing/red state the output must not carry. Scoped to state-asserting
# phrases rather than any occurrence of "failed"/"broken", so a green change that
# merely narrates the bug it fixed ("fixed the failing test; CI green") is NOT rejected.
_RED_BUILD = re.compile(
    r"(?i)\b("
    r"ci (?:is )?red|build (?:is )?(?:failing|broken|red)|"
    r"tests? (?:are |is )?(?:failing|red)|suite (?:is )?(?:red|failing)|"
    r"still (?:failing|broken|red)|no tests"
    r")\b",
)


def input_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    """Backend engineers accept any in-department, gate-clear ticket."""
    return default_input_guardrail(ctx)


def output_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    """Accept only a tested, green backend change (LAW 5 — green CI = done)."""
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
