"""Guardrail for the ``cpo`` role (DAS-1471).

INPUT: the shared scope screen (wrong-dept / missing-consumes / gate-open) is
sufficient — a CPO ticket is any product-dept strategy, scope, KPI, or roadmap
ticket, so no extra relevance screen is added.

OUTPUT: a CPO deliverable is only accepted when the produced work records an
explicit decision. This encodes the discipline's Definition of Done: "the
decision, plan, or ADR you own is made and recorded (ADR / board minutes /
approved queue), with the rationale and a law-check captured" (role overlay).
Notes or an undecided exploration are not a CPO decision.
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

ROLE = "cpo"

# Positive evidence that an explicit decision / approval was recorded.
_DECISION = re.compile(
    r"\b(decid\w*|decision|approv\w*|reject\w*|prioriti[sz]\w*|roadmap|"
    r"ratif\w*|green[- ]?light|sign[- ]?off|signed[- ]?off|greenlit)\b"
    r"|\bADR-\d+\b",
    re.IGNORECASE,
)


def input_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    """CPO accepts any in-department, gate-clear product ticket."""
    return default_input_guardrail(ctx)


def output_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    """Accept only a CPO deliverable that records an explicit decision."""
    ok, feedback = default_output_guardrail(ctx)
    if not ok:
        return (ok, feedback)
    output = ctx.output or ""
    if not _DECISION.search(output):
        return trip(
            "no decision recorded: a CPO deliverable must end in an explicit "
            "decision (decided / approved / rejected / prioritized / roadmap / "
            "ADR-NNNN) with the rationale; the output records none — make and "
            "record the call before it can be accepted."
        )
    return ok_result()
