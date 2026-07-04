"""Guardrail for the ``board-member`` role (DAS-1471 / R4 rollout 2->32).

INPUT: the shared scope screen (wrong-dept / missing-consumes / gate-open) is
sufficient — a board-member ticket is any governance-dept ticket routed to the
role by RACI; the department check already keeps out-of-scope work off the desk.

OUTPUT: a board-member's charter-guided review or vote is only accepted when the
produced work records an explicit decision — an approval, rejection, or vote —
not merely a discussion. This encodes the role's Definition of Done: "the
decision, plan, or ADR you own is made and recorded (ADR / board minutes /
approved queue), with the rationale and a law-check captured" (role overlay).
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

ROLE = "board-member"

# Positive evidence that a decision / vote was actually recorded — not merely a
# discussion. Kept broad and case-insensitive so legitimate minutes, ADRs, or
# approved-queue entries never trip; a marker anywhere in the output passes.
_DECISION_RECORDED = re.compile(
    r"\b("
    r"approv(?:e|ed|es|al)|reject(?:ed|s|ion)?|decid(?:e|ed|es)|decision|"
    r"ratif(?:y|ied|ies)|resolv(?:e|ed)|resolution|adopt(?:ed|s)?|endorse[ds]?|"
    r"second(?:ed)?|abstain(?:ed)?|vote[ds]?|"
    r"sign[- ]?off|signed[- ]?off|"
    r"board[- ]?minutes?|ruling|ADR|approved[- ]?queue|"
    r"TASDIQLANDI"
    r")\b",
    re.IGNORECASE,
)


def input_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    """Board members accept any in-department, gate-clear governance ticket."""
    return default_input_guardrail(ctx)


def output_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    """Accept only a review/vote that records an explicit decision."""
    ok, feedback = default_output_guardrail(ctx)
    if not ok:
        return (ok, feedback)
    if not _DECISION_RECORDED.search(ctx.output or ""):
        return trip(
            "no decision recorded: a board-member review/vote must end in an "
            "explicit decision (approve / reject / vote / ratified) captured in "
            "the minutes or ADR with rationale and a law-check; the output "
            "records only discussion, not a decision."
        )
    return ok_result()
