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

ROLE = "tech-writer"


_DOC_ARTIFACT = re.compile(
    r"\b(changelog|readme|documentation|docs?|document\w*|release[- ]notes|"
    r"migration[- ]guide|guide|tutorial|reference|handbook|how[- ]?to)\b"
    r"|\.(?:md|rst|mdx)\b|/docs?/",
    re.IGNORECASE,
)


def input_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    return default_input_guardrail(ctx)


def output_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    ok, feedback = default_output_guardrail(ctx)
    if not ok:
        return (ok, feedback)
    output = ctx.output or ""
    if not _DOC_ARTIFACT.search(output):
        return trip(
            "no doc artifact: a tech-writer deliverable must reference the "
            "documentation it produced (a changelog / README / docs page / "
            "release notes / guide / .md file); the output references none — "
            "write and cite the doc before it can be accepted."
        )
    return ok_result()
