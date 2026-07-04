"""Guardrail for the ``cdo`` role (design executive — DAS-1471 family).

INPUT: the shared scope screen (wrong-dept / missing-consumes / gate-open) is
sufficient for the CDO; a CDO ticket is any design-dept strategy / coordination
ticket, which is deliberately broad, so no extra keyword screen is layered on.

OUTPUT: a CDO deliverable is only accepted when the produced work records an
explicit decision. This encodes the discipline's Definition of Done — "the
decision, plan, or ADR you own is made and recorded (ADR / board minutes /
approved queue), with the rationale and a law-check captured" (role overlay). A
write-up that merely observes or gathers, with no decision landed, is not done.
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

ROLE = "cdo"

# Positive evidence that an explicit decision / approval was recorded. Kept
# broad and tolerant so any real decision write-up carries at least one marker.
_DECISION = re.compile(
    r"\b(decision|decided|decide|approv\w*|reject\w*|ratif\w*|endorse\w*|"
    r"greenlit|green[- ]?light|go[- ]?ahead|direction\s+set|sign[- ]?off|"
    r"signed[- ]?off|adr)\b",
    re.IGNORECASE,
)


def input_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    """The CDO accepts any in-department, gate-clear design ticket."""
    return default_input_guardrail(ctx)


def output_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    """Accept only a CDO write-up that lands an explicit, recorded decision."""
    ok, feedback = default_output_guardrail(ctx)
    if not ok:
        return (ok, feedback)
    output = ctx.output or ""
    if not _DECISION.search(output):
        return trip(
            "no decision recorded: a CDO deliverable must land an explicit "
            "decision / approval (decided / approved / rejected / ratified / ADR) "
            "with its rationale and law-check; the output records none — make the "
            "call and record it."
        )
    return ok_result()
