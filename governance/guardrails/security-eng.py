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

ROLE = "security-eng"


_SECURITY_TERMS = re.compile(
    r"\b(security|auth|secret|credential|vuln|cve|owasp|red[- ]?team|scan|"
    r"encryption|supply[- ]?chain|pentest|sast|dast|exploit|threat|compliance)\b",
    re.IGNORECASE,
)


_SCAN_EVIDENCE = re.compile(
    r"\b(scan(?:s|ned|ning)?|red[- ]?team|vuln(?:erabilit(?:y|ies))?|cve|"
    r"finding(?:s)?|sast|dast|gitleaks|owasp|remediat(?:e|ed|ion)|exploit|"
    r"pentest|threat[- ]?model)\b",
    re.IGNORECASE,
)


def input_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    ok, feedback = default_input_guardrail(ctx)
    if not ok:
        return (ok, feedback)
    haystack = f"{ctx.frontmatter.get('title', '')}\n{ctx.body}"
    if not _SECURITY_TERMS.search(haystack):
        return trip(
            "off-scope for security-eng: the ticket names no security concern "
            "(scan/red-team/vuln/auth/secrets/…); re-route to the owning "
            "engineering role."
        )
    return ok_result()


def output_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    ok, feedback = default_output_guardrail(ctx)
    if not ok:
        return (ok, feedback)
    output = (ctx.output or "").strip()
    if not _SCAN_EVIDENCE.search(output):
        return trip(
            "no scan evidence: a security-eng deliverable must report a scan or "
            "red-team result — a finding count (including zero findings), a CVE, "
            "or a remediation; the output records none — run the scan and report "
            "the findings before it can be accepted."
        )
    return ok_result()
