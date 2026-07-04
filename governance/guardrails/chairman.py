"""Guardrail for the ``chairman`` role (DAS-1471 / R4 rollout 2->32).

INPUT: the shared scope screen (wrong-dept / missing-consumes / gate-open) is
sufficient — a Chairman ticket is any governance-dept ticket routed to the role
by RACI; the department check already keeps out-of-scope work off the desk.

OUTPUT: a Chairman's charter/governance ruling or binding board minute is only
accepted when the produced work records an explicit ruling — ruled, ratified,
approved, upheld, or overruled — not merely a session summary. This encodes the
role's Definition of Done: "the decision, plan, or ADR you own is made and
recorded (ADR / board minutes / approved queue), with the rationale and a
law-check captured" (role overlay).
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

ROLE = "chairman"

# Positive evidence that a binding ruling / decision was actually recorded — not
# merely a session opened or discussion adjourned. Kept broad and
# case-insensitive so legitimate board minutes, an ADR, or an approved-queue
# entry never trips.
_RULING_RECORDED = re.compile(
    r"\b("
    r"rul(?:e|ed|es|ing)|approv(?:e|ed|es|al)|reject(?:ed|s|ion)?|"
    r"decid(?:e|ed|es)|decision|ratif(?:y|ied|ies)|resolv(?:e|ed)|resolution|"
    r"adopt(?:ed|s)?|uphold|upheld|overrul(?:e|ed|es)|"
    r"sign[- ]?off|signed[- ]?off|"
    r"board[- ]?minutes?|ADR|approved[- ]?queue|"
    r"TASDIQLANDI"
    r")\b",
    re.IGNORECASE,
)


def input_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    """The Chairman accepts any in-department, gate-clear governance ticket."""
    return default_input_guardrail(ctx)


def output_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    """Accept only a governance ruling that records an explicit, binding decision."""
    ok, feedback = default_output_guardrail(ctx)
    if not ok:
        return (ok, feedback)
    if not _RULING_RECORDED.search(ctx.output or ""):
        return trip(
            "no ruling recorded: a Chairman ruling or board minute must record an "
            "explicit decision (ruled / ratified / approved / upheld / overruled) "
            "with binding effect in the minutes or an ADR, with rationale and a "
            "law-check; the output records only a session summary, not a ruling."
        )
    return ok_result()
