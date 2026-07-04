"""Guardrail for the ``cto`` role (R4 rollout 2->32).

INPUT: the shared scope screen (wrong-dept / missing-consumes / gate-open) is
sufficient; the CTO fields a broad range of engineering decisions, so no extra
input relevance screen is imposed (a narrow keyword screen would false-trip on
legitimate cross-cutting work).

OUTPUT: a CTO deliverable is only accepted when the produced work records an
explicit decision / approval — a made-and-recorded call (ADR, RFC, board
minutes, approved queue, or a stated decision). This encodes the CTO's
Definition of Done ("the decision, plan, or ADR you own is made and recorded ...
with the rationale and a law-check captured") so a deliberation that reaches no
recorded decision never passes the tripwire.
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

ROLE = "cto"

# Positive evidence that an explicit decision / approval was recorded.
_DECISION = re.compile(
    r"\b(decision|decided|decide|approv(?:e|ed|al)|reject(?:ed|ion)?|"
    r"adr|rfc|ratif(?:y|ied)|sign(?:ed)?[- ]?off|"
    r"recommend(?:ed|ation)?|select(?:ed|ion)?|chos(?:e|en)|"
    r"go[- ]?ahead|approved[- ]?queue|board[- ]?minutes)\b",
    re.IGNORECASE,
)


def input_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    """The CTO accepts any in-department, gate-clear decision ticket."""
    return default_input_guardrail(ctx)


def output_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    """Accept only a deliverable that records an explicit decision / approval."""
    ok, feedback = default_output_guardrail(ctx)
    if not ok:
        return (ok, feedback)
    if not _DECISION.search(ctx.output or ""):
        return trip(
            "no decision recorded: a CTO deliverable must land an explicit, "
            "recorded call (ADR / RFC / board minutes / approved queue, or a "
            "stated decision / approval) with rationale and a law-check; the "
            "output records none — make and record the decision."
        )
    return ok_result()
