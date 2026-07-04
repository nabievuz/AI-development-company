"""Guardrail for the ``qa-lead`` role (R4 rollout — DAS-1471).

INPUT: the shared scope screen (wrong-dept / missing-consumes / gate-open) is
sufficient; a QA-Lead ticket is any engineering-dept ticket routed to this role.

OUTPUT: the QA Lead owns GATE-4 (eval thresholds, release-blocking judgment), so
the work is only accepted when it records an **explicit gate decision** — an
eval PASS or a release BLOCK — not just an observation. This encodes the Lead
Definition of Done ("the gate you own is explicitly passed or blocked, with the
evidence and the decision recorded").
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

ROLE = "qa-lead"

# An explicit GATE-4 / eval decision the output MUST record (pass or block).
# Tolerant + case-insensitive so a legitimate gate report never false-trips.
_GATE4_DECISION = re.compile(
    r"\b(gate[- ]?4|threshold|pass(?:ed|es)?|block(?:ed|ing|er)?|"
    r"release[- ]?block(?:ing|er)?|approv(?:e|ed|al)|no[- ]?go|go[- ]?live|"
    r"sign[- ]?off|signed[- ]?off)\b",
    re.IGNORECASE,
)


def input_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    """QA Lead accepts any in-department, gate-clear ticket."""
    return default_input_guardrail(ctx)


def output_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    """Accept only a GATE-4 judgment that records an explicit pass/block decision."""
    ok, feedback = default_output_guardrail(ctx)
    if not ok:
        return (ok, feedback)
    output = (ctx.output or "").strip()
    if not _GATE4_DECISION.search(output):
        return trip(
            "no gate decision: a GATE-4 eval judgment must end in an explicit "
            "decision (threshold passed / release blocked / no-go) with the "
            "evidence; the output records none — state the decision."
        )
    return ok_result()
