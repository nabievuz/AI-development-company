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


_LEGAL_TERMS = re.compile(
    r"\b(legal|complian\w*|privacy|gdpr|ccpa|hipaa|soc\s?2|license|licence|"
    r"licens\w*|contract|terms|policy|policies|regulat\w*|liabilit\w*|"
    r"copyright|trademark|data[- ]?protection|consent|ethics|dpa|dpia|"
    r"retention|jurisdiction)\b",
    re.IGNORECASE,
)


_COMPLIANCE_REF = re.compile(
    r"\b(gdpr|ccpa|hipaa|soc\s?2|iso\s?\d|pci|dpa|dpia|compl(?:iance|iant)|"
    r"regulat(?:ion|ory)|statute|clause|licen[cs]e|terms|privacy|policy|"
    r"policies|contract|article\s?\d|section\s?\d|citation|cite[ds]?)\b|§",
    re.IGNORECASE,
)


def input_guardrail(ctx: GuardrailContext) -> GuardrailResult:
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
