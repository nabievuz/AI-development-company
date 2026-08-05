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


_DESIGN_ARTIFACT = re.compile(
    r"\b(mockup|wireframe|prototype|figma|component|token|design[- ]?system|"
    r"spec|handoff|hand[- ]?off|redline|style[- ]?guide|artifact|screen)\b",
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
            "no design artifact: a design-lead deliverable must produce or hand "
            "off a concrete artifact / spec (mockup / component / token / Figma / "
            "spec / handoff); the output references none — attach the artifact and "
            "the build spec before it can be accepted."
        )
    return ok_result()
