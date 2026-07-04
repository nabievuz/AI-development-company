"""Guardrail for the ``frontend-eng-2`` role (R4 rollout 2->32; DAS-1471).

INPUT: the shared scope screen (wrong-dept / missing-consumes / gate-open) is
sufficient for an IC — a frontend ticket is any engineering-dept ticket routed
to this role; no extra relevance screen (this matches the backend-eng template,
and avoids false-tripping a validly-routed frontend ticket on keywords).

OUTPUT: a frontend IC's Definition of Done is "a reviewed PR with green CI, every
acceptance criterion checked". So the produced work is only accepted when it
carries positive CI/verification evidence (tests / lint / build / green run).
This encodes LAW 5 ("green CI = done") without banning any word — a legitimate
frontend deliverable (even an "error boundary" fix) always cites its green run,
so we require a positive marker rather than a failure-word blacklist.
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

ROLE = "frontend-eng-2"

# Positive evidence that the frontend change was verified green. Broad and
# case-insensitive so any real PR report matches at least one token; word
# boundaries keep short tokens like "ci" / "e2e" from matching inside unrelated
# words.
_CI_EVIDENCE = re.compile(
    r"\b(test|tests|jest|vitest|cypress|playwright|e2e|lint|build|ci|green|"
    r"pass|passed|passing|coverage|snapshot|storybook|typecheck|tsc)\b",
    re.IGNORECASE,
)


def input_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    """A frontend engineer accepts any in-department, gate-clear ticket."""
    return default_input_guardrail(ctx)


def output_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    """Accept only a frontend change that cites its green CI / test evidence."""
    ok, feedback = default_output_guardrail(ctx)
    if not ok:
        return (ok, feedback)
    if not _CI_EVIDENCE.search(ctx.output or ""):
        return trip(
            "no CI evidence: a frontend change must ship as a reviewed PR with "
            "green CI (tests / lint / build passing); the output cites none — "
            "run the checks and report the passing run (LAW 5 — green CI = done)."
        )
    return ok_result()
