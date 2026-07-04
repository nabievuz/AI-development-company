"""Guardrail for the ``sre-lead`` role (R4 rollout — DAS-1471).

INPUT: the shared scope screen (wrong-dept / missing-consumes / gate-open) is
sufficient; an SRE-Lead ticket is any engineering-dept ticket routed to this role.

OUTPUT: the SRE / DevOps Lead owns GATE-5 (production launch, observability
sign-off, prod blast radius), so the work is only accepted when it records an
**explicit launch decision** — a GO-live / sign-off / approval, or an explicit
BLOCK / no-go. This encodes the Lead Definition of Done ("the gate you own is
explicitly passed or blocked, with the evidence and the decision recorded").
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

ROLE = "sre-lead"

# An explicit GATE-5 launch / deploy decision the output MUST record. Tolerant +
# case-insensitive so a legitimate go-live sign-off never false-trips.
_GATE5_DECISION = re.compile(
    r"\b(gate[- ]?5|sign[- ]?off|signed[- ]?off|approv(?:e|ed|al)|"
    r"block(?:ed|ing|er)?|go[- ]?live|no[- ]?go|launch(?:ed)?|roll[- ]?back|"
    r"deploy(?:ment)?[- ]?approved|observability)\b",
    re.IGNORECASE,
)


def input_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    """SRE Lead accepts any in-department, gate-clear ticket."""
    return default_input_guardrail(ctx)


def output_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    """Accept only a GATE-5 launch judgment that records an explicit go/no-go decision."""
    ok, feedback = default_output_guardrail(ctx)
    if not ok:
        return (ok, feedback)
    output = (ctx.output or "").strip()
    if not _GATE5_DECISION.search(output):
        return trip(
            "no launch decision: a GATE-5 production-launch judgment must end in "
            "an explicit decision (go-live / sign-off / approved, or blocked / "
            "no-go) with the observability evidence; the output records none — "
            "state the decision."
        )
    return ok_result()
