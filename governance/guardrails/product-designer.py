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


_DESIGN_ARTIFACT = re.compile(
    r"\b(mockup|wireframe|prototype|figma|component|token|design[- ]?system|"
    r"variant|screen|frame|artboard|icon|style[- ]?guide|spec)\b",
    re.IGNORECASE,
)


def input_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    return default_input_guardrail(ctx)


def output_guardrail(ctx: GuardrailContext) -> GuardrailResult:
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
