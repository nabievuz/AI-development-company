"""Guardrail for the ``content-lead`` role (marketing — DAS-1471).

INPUT: the shared scope screen (wrong-dept / missing-consumes / gate-open) is
sufficient — a content-lead ticket is any marketing-dept content ticket, so no
extra relevance screen is layered on.

OUTPUT: a content deliverable is only accepted when the produced work references
a concrete content artifact (a draft / post / copy / doc / changelog entry).
This encodes the discipline's Definition of Done: "the content is produced,
on-brand, reviewed, and the ticket updated" (role overlay) — a vague opinion
about messaging with no produced artifact is not done.
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

ROLE = "content-lead"

# Positive evidence that a concrete content artifact was produced.
_CONTENT_ARTIFACT = re.compile(
    r"\b(drafts?|drafted|publish(?:ed)?|article|blog|posts?|copy|headline|"
    r"word[- ]?count|changelog|newsletter|landing[- ]?page|content[- ]?calendar|"
    r"caption|script|whitepaper)\b|\.md\b",
    re.IGNORECASE,
)


def input_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    """The content lead accepts any in-department, gate-clear marketing ticket."""
    return default_input_guardrail(ctx)


def output_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    """Accept only content work that references a produced artifact."""
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
