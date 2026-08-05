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

ROLE = "content-lead"


_CONTENT_ARTIFACT = re.compile(
    r"\b(drafts?|drafted|publish(?:ed)?|article|blog|posts?|copy|headline|"
    r"word[- ]?count|changelog|newsletter|landing[- ]?page|content[- ]?calendar|"
    r"caption|script|whitepaper)\b|\.md\b",
    re.IGNORECASE,
)


def input_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    return default_input_guardrail(ctx)


def output_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    ok, feedback = default_output_guardrail(ctx)
    if not ok:
        return (ok, feedback)
    output = (ctx.output or "").strip()
    if not _CONTENT_ARTIFACT.search(output):
        return trip(
            "no content artifact: a content deliverable must reference the "
            "produced work (a draft / post / copy / article / changelog entry or "
            "a saved doc such as a .md file); the output references none — "
            "produce the artifact and cite it."
        )
    return ok_result()
