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


_DECISION = re.compile(
    r"\b(decision|decided|decide|approv(?:e|ed|al)|reject(?:ed|ion)?|"
    r"adr|rfc|ratif(?:y|ied)|sign(?:ed)?[- ]?off|"
    r"recommend(?:ed|ation)?|select(?:ed|ion)?|chos(?:e|en)|"
    r"go[- ]?ahead|approved[- ]?queue|board[- ]?minutes)\b",
    re.IGNORECASE,
)


def input_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    return default_input_guardrail(ctx)


def output_guardrail(ctx: GuardrailContext) -> GuardrailResult:
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
