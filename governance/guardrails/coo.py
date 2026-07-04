"""Guardrail for the ``coo`` role (R4 — rollout 2->32).

INPUT: the shared scope screen (wrong-dept / missing-consumes / gate-open) is
sufficient for the COO — the role owns operations decisions broadly, so there is
no narrower relevance screen to add.

OUTPUT: a COO deliverable is only accepted when the produced work records an
explicit decision or approval. This encodes the discipline's Definition of Done:
"the decision, plan, or ADR you own is made and recorded (ADR / board minutes /
approved queue), with the rationale and a law-check captured" (role overlay) — a
memo that merely gathers options without deciding is not done.
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

ROLE = "coo"

# Positive evidence that an explicit decision / approval was recorded.
_DECISION = re.compile(
    r"\b(decision|decided|decide|approv(?:e|ed|al)|reject(?:ed|s)?|"
    r"adr|go[- ]?ahead|no[- ]?go|greenlit|greenlight|ratif(?:y|ied)|"
    r"plan[- ]of[- ]record|sign[- ]?off|signed[- ]?off|authoriz(?:e|ed))\b",
    re.IGNORECASE,
)


def input_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    """The COO accepts any in-department, gate-clear operations ticket."""
    return default_input_guardrail(ctx)


def output_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    """Accept only a COO deliverable that records an explicit decision."""
    ok, feedback = default_output_guardrail(ctx)
    if not ok:
        return (ok, feedback)
    output = (ctx.output or "").strip()
    if not _DECISION.search(output):
        return trip(
            "no decision recorded: a COO deliverable must end in an explicit "
            "decision or approval (decided / approved / go / no-go / signed-off) "
            "with the rationale captured; the output records none — make the call "
            "and record it (ADR / board minutes / approved queue)."
        )
    return ok_result()
