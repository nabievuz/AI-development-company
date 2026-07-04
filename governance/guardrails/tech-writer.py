"""Guardrail for the ``tech-writer`` role (DAS-1471).

INPUT: the shared scope screen (wrong-dept / missing-consumes / gate-open) is
sufficient — a tech-writer ticket is any product-dept doc / changelog ticket.

OUTPUT: a tech-writer deliverable is only accepted when it references a concrete
documentation artifact (a changelog / README / docs page / release notes /
guide). This encodes the discipline's Definition of Done: "the doc/changelog is
written, accurate to the shipped behaviour, and the ticket updated" (role
overlay). A conversation summary with no doc artifact is not a doc deliverable.
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

ROLE = "tech-writer"

# Positive evidence that a documentation / changelog artifact was produced.
_DOC_ARTIFACT = re.compile(
    r"\b(changelog|readme|documentation|docs?|document\w*|release[- ]notes|"
    r"migration[- ]guide|guide|tutorial|reference|handbook|how[- ]?to)\b"
    r"|\.(?:md|rst|mdx)\b|/docs?/",
    re.IGNORECASE,
)


def input_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    """Technical writers accept any in-department, gate-clear product ticket."""
    return default_input_guardrail(ctx)


def output_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    """Accept only a tech-writer deliverable that references a doc artifact."""
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
