"""Guardrail for the ``sre-eng`` role (R4 rollout — DAS-1471).

INPUT: the shared scope screen (wrong-dept / missing-consumes / gate-open) is
sufficient; an SRE ticket is any engineering-dept ticket routed to this role.

OUTPUT: the SRE Engineer is **rollback-first** and owns runbooks, deploy
mechanics, and monitoring wiring, so a deploy/ops change is only accepted when
the work references a **rollback / runbook / health-check / monitoring** control.
This encodes the SRE Definition of Done at the guardrail layer so a bare "shipped
to prod" with no operational safety net never passes the tripwire.
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

ROLE = "sre-eng"

# Positive evidence of an operational safety net (rollback-first discipline).
# Tolerant + case-insensitive: a real SRE deliverable names at least one.
_SRE_EVIDENCE = re.compile(
    r"\b(roll[- ]?back|run[- ]?book|health[- ]?check|healthcheck|"
    r"monitor(?:ing|s)?|observability|alert(?:ing|s)?|dashboard|on[- ]?call|"
    r"revert|canary)\b",
    re.IGNORECASE,
)


def input_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    """SRE engineers accept any in-department, gate-clear ticket."""
    return default_input_guardrail(ctx)


def output_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    """Accept only an ops change that names a rollback / runbook / monitoring control."""
    ok, feedback = default_output_guardrail(ctx)
    if not ok:
        return (ok, feedback)
    output = (ctx.output or "").strip()
    if not _SRE_EVIDENCE.search(output):
        return trip(
            "no rollback/runbook/monitoring: an SRE deploy or ops change is "
            "rollback-first and must reference a rollback path, a runbook, a "
            "health-check, or monitoring/alerting; the output names none — add "
            "the operational safety net before it can be accepted."
        )
    return ok_result()
