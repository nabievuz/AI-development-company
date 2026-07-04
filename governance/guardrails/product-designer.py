"""Guardrail for the ``product-designer`` role (design-dept — DAS-1471 family).

INPUT: the shared scope screen (wrong-dept / missing-consumes / gate-open) is
sufficient; a product-designer ticket is any design-dept ticket, and a broad
keyword screen would risk falsely refusing a legitimate design ticket, so none
is layered on.

OUTPUT: a product-designer deliverable is only accepted when the produced work
references a concrete visual artifact. This encodes the discipline's Definition
of Done — "the design artifact is produced, token-compliant, reviewed, and
handed to engineering with the spec it needs to build" (role overlay), whose
mission is "mockups, components, design tokens — visually checked".
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

ROLE = "product-designer"

# Positive evidence that a concrete visual artifact was produced. Broad and
# tolerant so any real mockup / component / token deliverable carries a marker.
_DESIGN_ARTIFACT = re.compile(
    r"\b(mockup|wireframe|prototype|figma|component|token|design[- ]?system|"
    r"variant|screen|frame|artboard|icon|style[- ]?guide|spec)\b",
    re.IGNORECASE,
)


def input_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    """The Product Designer accepts any in-department, gate-clear ticket."""
    return default_input_guardrail(ctx)


def output_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    """Accept only a product-designer deliverable that references an artifact."""
    ok, feedback = default_output_guardrail(ctx)
    if not ok:
        return (ok, feedback)
    output = ctx.output or ""
    if not _DESIGN_ARTIFACT.search(output):
        return trip(
            "no design artifact: a product-designer deliverable must produce a "
            "concrete visual artifact (mockup / component / token / screen / Figma "
            "frame); the output references none — attach the artifact before it "
            "can be accepted."
        )
    return ok_result()
