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


_SRE_EVIDENCE = re.compile(
    r"\b(roll[- ]?back|run[- ]?book|health[- ]?check|healthcheck|"
    r"monitor(?:ing|s)?|observability|alert(?:ing|s)?|dashboard|on[- ]?call|"
    r"revert|canary)\b",
    re.IGNORECASE,
)


def input_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    return default_input_guardrail(ctx)


def output_guardrail(ctx: GuardrailContext) -> GuardrailResult:
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
