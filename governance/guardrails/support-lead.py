"""Guardrail for the ``support-lead`` role (R4 — rollout 2->32).

INPUT: the shared scope screen (wrong-dept / missing-consumes / gate-open) is
sufficient — support triage spans the whole operations inbox, so there is no
narrower relevance screen to add.

OUTPUT: a support deliverable is only accepted when the produced work shows the
item was actually triaged, resolved, or routed. This encodes the discipline's
Definition of Done: "the support item is triaged and resolved or routed within
SLA, and recurring issues are filed back to the owning team as tickets" (role
overlay) — an update that merely restates the complaint is not a resolution.
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

ROLE = "support-lead"

# Positive evidence that the item was triaged / resolved / routed within SLA.
_RESOLUTION = re.compile(
    r"\b(triag(?:e|ed|ing)|resolv(?:e|ed|ing)|resolution|routed|route[d]?|"
    r"escalat(?:e|ed|ion)|closed|answered|responded|repl(?:y|ied)|"
    r"acknowledg\w*|workaround|dispatched|filed|sla)\b",
    re.IGNORECASE,
)

# An explicitly UNRESOLVED / still-open state that must trip even when a resolution
# verb appears in a NEGATED or future sense ("not yet resolved", "no workaround").
_UNRESOLVED = re.compile(
    r"(?i)\b(?:not (?:yet )?(?:resolv|triag|clos|dispatch)\w*|unresolved|"
    r"still (?:investigating|open|pending|unresolved)|no (?:workaround|resolution|fix)\b)",
)


def input_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    """Support triage accepts any in-department, gate-clear operations ticket."""
    return default_input_guardrail(ctx)


def output_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    """Accept only a support deliverable that shows triage / resolution / routing."""
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
