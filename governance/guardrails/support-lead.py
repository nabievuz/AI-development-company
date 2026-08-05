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

ROLE = "support-lead"


_RESOLUTION = re.compile(
    r"\b(triag(?:e|ed|ing)|resolv(?:e|ed|ing)|resolution|routed|route[d]?|"
    r"escalat(?:e|ed|ion)|closed|answered|responded|repl(?:y|ied)|"
    r"acknowledg\w*|workaround|dispatched|filed|sla)\b",
    re.IGNORECASE,
)


_UNRESOLVED = re.compile(
    r"(?i)\b(?:not (?:yet )?(?:resolv|triag|clos|dispatch)\w*|unresolved|"
    r"still (?:investigating|open|pending|unresolved)|no (?:workaround|resolution|fix)\b)",
)


def input_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    return default_input_guardrail(ctx)


def output_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    ok, feedback = default_output_guardrail(ctx)
    if not ok:
        return (ok, feedback)
    output = (ctx.output or "").strip()
    if _UNRESOLVED.search(output):
        return trip(
            "still unresolved: the output reports the item as not yet resolved / "
            "still open (a negated or future disposition); an accepted support "
            "deliverable must record an actual triage / resolution / routing outcome."
        )
    if not _RESOLUTION.search(output):
        return trip(
            "no resolution recorded: a support deliverable must show the item was "
            "triaged, resolved, routed, or escalated (with SLA noted) — the output "
            "restates the issue without disposition; triage and record the outcome."
        )
    return ok_result()
