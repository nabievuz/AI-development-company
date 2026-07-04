"""Guardrail for the ``design-lead`` role (design-dept — DAS-1471 family).

INPUT: the shared scope screen (wrong-dept / missing-consumes / gate-open) is
sufficient; a design-lead ticket is any design-dept ticket, and a broad keyword
screen would risk falsely refusing a legitimate design ticket, so none is added.

OUTPUT: a design-lead deliverable is only accepted when the produced work
references a concrete design artifact / spec. This encodes the discipline's
Definition of Done — "the design artifact is produced, token-compliant,
reviewed, and handed to engineering with the spec it needs to build" (role
overlay). A status note with no artifact or spec reference is not a handoff.
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

ROLE = "design-lead"

# Positive evidence that a concrete design artifact / spec was produced or
# handed off. Broad and tolerant so any real design deliverable carries one.
_DESIGN_ARTIFACT = re.compile(
    r"\b(mockup|wireframe|prototype|figma|component|token|design[- ]?system|"
    r"spec|handoff|hand[- ]?off|redline|style[- ]?guide|artifact|screen)\b",
    re.IGNORECASE,
)


def input_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    """The Design Lead accepts any in-department, gate-clear design ticket."""
    return default_input_guardrail(ctx)


def output_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    """Accept only a design-lead deliverable that references an artifact / spec."""
    ok, feedback = default_output_guardrail(ctx)
    if not ok:
        return (ok, feedback)
    output = ctx.output or ""
    if not _DESIGN_ARTIFACT.search(output):
        return trip(
            "no design artifact: a design-lead deliverable must produce or hand "
            "off a concrete artifact / spec (mockup / component / token / Figma / "
            "spec / handoff); the output references none — attach the artifact and "
            "the build spec before it can be accepted."
        )
    return ok_result()
