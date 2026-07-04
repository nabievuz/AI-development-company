"""Guardrail for the ``senior-pm`` role (DAS-1471).

INPUT: the shared scope screen (wrong-dept / missing-consumes / gate-open) is
sufficient — a senior-PM ticket is any product-dept spec / PRD ticket.

OUTPUT: a senior-PM deliverable is only accepted when it references a concrete
PRD / spec / requirements artifact. This encodes the discipline's Definition of
Done: the role is "PRD authoring (GATE-1 responsible) — ambiguity here
multiplies downstream" (role overlay), and the product charter requires "every
shipped feature has a spec in specs/". Brainstorm notes are not a PRD.
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

ROLE = "senior-pm"

# Positive evidence that a PRD / spec / requirements artifact was produced.
_PRD_ARTIFACT = re.compile(
    r"\b(prd|spec|specs|specification|requirement\w*|acceptance[- ]criteri\w*|"
    r"user stor(?:y|ies)|success metric\w*)\b"
    r"|\bADR-\d+\b|/specs?/",
    re.IGNORECASE,
)


def input_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    """Senior PM accepts any in-department, gate-clear product ticket."""
    return default_input_guardrail(ctx)


def output_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    """Accept only a senior-PM deliverable that produces a PRD / spec artifact."""
    ok, feedback = default_output_guardrail(ctx)
    if not ok:
        return (ok, feedback)
    output = ctx.output or ""
    if not _PRD_ARTIFACT.search(output):
        return trip(
            "no spec artifact: a senior-PM deliverable must produce a concrete "
            "PRD / spec / requirements artifact (requirements, acceptance "
            "criteria, user stories, success metrics, specs/…); the output "
            "records none — write the spec before it can be accepted (GATE-1)."
        )
    return ok_result()
