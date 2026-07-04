"""Guardrail for the ``legal-analyst`` role (R4 — rollout 2->32).

INPUT: the shared scope screen plus a legal-relevance screen — a legal /
compliance ticket must actually name a legal, compliance, privacy, or contractual
concern, mirroring security-lead's terms screen for its specialist discipline.

OUTPUT: a legal / compliance review is only accepted when the produced work
anchors its conclusion to a compliance standard or citation (GDPR / SOC2 / a
clause / a policy / a regulation). This encodes the discipline's Definition of
Done — "the analysis is delivered with sourced findings and a clear, actionable
recommendation" over a "risk-ethics review" (role overlay): a legal opinion with
no reference is unsourced and cannot be accepted.
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

ROLE = "legal-analyst"

# A legal ticket names at least one legal / compliance concern in its scope.
_LEGAL_TERMS = re.compile(
    r"\b(legal|complian\w*|privacy|gdpr|ccpa|hipaa|soc\s?2|license|licence|"
    r"licens\w*|contract|terms|policy|policies|regulat\w*|liabilit\w*|"
    r"copyright|trademark|data[- ]?protection|consent|ethics|dpa|dpia|"
    r"retention|jurisdiction)\b",
    re.IGNORECASE,
)

# Positive evidence that the conclusion is anchored to a compliance standard or
# citation — a named regime, an instrument, or an explicit citation.
_COMPLIANCE_REF = re.compile(
    r"\b(gdpr|ccpa|hipaa|soc\s?2|iso\s?\d|pci|dpa|dpia|compl(?:iance|iant)|"
    r"regulat(?:ion|ory)|statute|clause|licen[cs]e|terms|privacy|policy|"
    r"policies|contract|article\s?\d|section\s?\d|citation|cite[ds]?)\b|§",
    re.IGNORECASE,
)


def input_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    """Shared scope screen + a legal-relevance screen."""
    ok, feedback = default_input_guardrail(ctx)
    if not ok:
        return (ok, feedback)
    haystack = f"{ctx.frontmatter.get('title', '')}\n{ctx.body}"
    if not _LEGAL_TERMS.search(haystack):
        return trip(
            "off-scope for legal-analyst: the ticket names no legal / compliance "
            "concern (legal/compliance/privacy/GDPR/license/contract/terms); "
            "re-route to the owning operations role."
        )
    return ok_result()


def output_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    """Accept only a legal review anchored to a compliance standard or citation."""
    ok, feedback = default_output_guardrail(ctx)
    if not ok:
        return (ok, feedback)
    output = (ctx.output or "").strip()
    if not _COMPLIANCE_REF.search(output):
        return trip(
            "unsourced legal review: the conclusion cites no compliance standard "
            "or reference (a regime like GDPR/SOC2, a clause, a policy, or a "
            "citation); anchor the finding to a source before it can be accepted."
        )
    return ok_result()
