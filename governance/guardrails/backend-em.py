"""Guardrail for the ``backend-em`` role (R4 rollout 2->32).

INPUT: the shared scope screen (wrong-dept / missing-consumes / gate-open) is
sufficient for an engineering manager; a backend-EM ticket is any
engineering-dept review / merge ticket.

OUTPUT: a code review is only accepted when the produced work records an
explicit review decision — a merge / approval OR a return-with-change-requests.
This encodes the EM's Definition of Done ("each ``in_review`` ticket you own is
either merged (GATE-3, green CI) or returned with concrete change requests") so
a review that states no verdict never passes the tripwire.
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

ROLE = "backend-em"

# Positive evidence that the review reached an explicit verdict.
_REVIEW_DECISION = re.compile(
    r"\b(approv(?:e|ed|al)|lgtm|merg(?:e|ed|ing)|"
    r"request(?:ing|ed)?[- ]?changes|changes[- ]?requested|change[- ]?request|"
    r"returned[- ]to[- ]author|reject(?:ed)?|needs[- ]?work|"
    r"sign(?:ed)?[- ]?off)\b",
    re.IGNORECASE,
)


def input_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    """Backend EMs accept any in-department, gate-clear review ticket."""
    return default_input_guardrail(ctx)


def output_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    """Accept only a review that records an explicit merge / change-request verdict."""
    ok, feedback = default_output_guardrail(ctx)
    if not ok:
        return (ok, feedback)
    if not _REVIEW_DECISION.search(ctx.output or ""):
        return trip(
            "no review decision recorded: a code review must end in an explicit "
            "verdict (approved / merged, or changes-requested / returned / "
            "blocked); the output records none — state the merge-or-return "
            "decision before it can be accepted."
        )
    return ok_result()
