"""Guardrail for the ``cmo`` role (marketing — DAS-1471).

INPUT: the shared scope screen (wrong-dept / missing-consumes / gate-open) is
sufficient for the CMO — a CMO ticket is any marketing-dept coordination or
decision ticket, so no extra relevance screen is layered on.

OUTPUT: a CMO deliverable is only accepted when the produced work records an
explicit decision. This is the discipline's Definition of Done: "the decision,
plan, or ADR you own is made and recorded (ADR / board minutes / approved
queue), with the rationale and a law-check captured" (role overlay) — a
narrative with no decision recorded is not done.
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

ROLE = "cmo"

# Positive evidence that an explicit decision / approval was recorded.
_DECISION_RECORDED = re.compile(
    r"\b(approved?|rejected?|decision|decided|sign[- ]?off|signed[- ]?off|"
    r"go[- ]?no[- ]?go|green[- ]?light(?:ed)?|greenlit|recommend(?:ation|ed|s)?|"
    r"adr|board[- ]?minutes|approved[- ]?queue)\b",
    re.IGNORECASE,
)


def input_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    """The CMO accepts any in-department, gate-clear marketing ticket."""
    return default_input_guardrail(ctx)


def output_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    """Accept only a CMO deliverable that records an explicit decision."""
    ok, feedback = default_output_guardrail(ctx)
    if not ok:
        return (ok, feedback)
    output = (ctx.output or "").strip()
    if not _DECISION_RECORDED.search(output):
        return trip(
            "no decision recorded: a CMO deliverable must end in an explicit "
            "decision (approved / rejected / signed-off / go-no-go / a recorded "
            "ADR or board-minutes entry); the output records none — state the "
            "decision with its rationale."
        )
    return ok_result()
