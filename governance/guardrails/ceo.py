"""Guardrail for the ``ceo`` role (DAS-1471 / R4 rollout 2->32).

INPUT: the shared scope screen (wrong-dept / missing-consumes / gate-open) is
sufficient — a CEO ticket is any governance-dept ticket routed to the role by
RACI; the department check already keeps out-of-scope work off the desk.

OUTPUT: a CEO's strategy call, goal decomposition, or cross-dept arbitration is
only accepted when the produced work records an explicit decision — approved,
decided, arbitrated, or ratified — not merely an exploration of options. This
encodes the role's Definition of Done: "the decision, plan, or ADR you own is
made and recorded (ADR / board minutes / approved queue), with the rationale and
a law-check captured" (role overlay).
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

ROLE = "ceo"

# Positive evidence that a strategy / arbitration decision was actually made and
# recorded — not merely options weighed. Kept broad and case-insensitive so a
# legitimate strategy note, ADR, or approved-queue entry never trips.
_DECISION_RECORDED = re.compile(
    r"\b("
    r"approv(?:e|ed|es|al)|reject(?:ed|s|ion)?|decid(?:e|ed|es)|decision|"
    r"ratif(?:y|ied|ies)|resolv(?:e|ed)|resolution|adopt(?:ed|s)?|endorse[ds]?|"
    r"arbitrat(?:e|ed|ion)|directive|mandate[ds]?|"
    r"sign[- ]?off|signed[- ]?off|approved[- ]?queue|"
    r"board[- ]?minutes?|ADR|"
    r"TASDIQLANDI"
    r")\b",
    re.IGNORECASE,
)


def input_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    """The CEO accepts any in-department, gate-clear governance ticket."""
    return default_input_guardrail(ctx)


def output_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    """Accept only strategy/arbitration work that records an explicit decision."""
    ok, feedback = default_output_guardrail(ctx)
    if not ok:
        return (ok, feedback)
    if not _DECISION_RECORDED.search(ctx.output or ""):
        return trip(
            "no decision recorded: a CEO strategy call or arbitration must end "
            "in an explicit decision (approved / decided / arbitrated / ratified) "
            "captured in an ADR, board minutes, or the approved queue with "
            "rationale and a law-check; the output records only options, not a "
            "decision."
        )
    return ok_result()
