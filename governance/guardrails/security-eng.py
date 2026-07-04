"""Guardrail for the ``security-eng`` role (R4 rollout — DAS-1471).

INPUT: reuses the shared scope screen (wrong-dept / missing-consumes /
gate-open), then adds a security-relevance refusal: a security-eng ticket must
actually be a security ticket (red-team / scans / vuln work).

OUTPUT: the Security Engineer runs red-team execution and scans, so the work is
only accepted when it reports **scan / red-team finding evidence** — a scan
result, a finding count (including zero), or a remediation. This encodes the
discipline's Definition of Done so a hand-wave "looks secure" with no scan
artifact never passes the tripwire.
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

ROLE = "security-eng"

# A security ticket names at least one security concern somewhere in its scope.
_SECURITY_TERMS = re.compile(
    r"\b(security|auth|secret|credential|vuln|cve|owasp|red[- ]?team|scan|"
    r"encryption|supply[- ]?chain|pentest|sast|dast|exploit|threat|compliance)\b",
    re.IGNORECASE,
)

# Positive evidence that a scan / red-team pass was executed with a result.
# Tolerant + case-insensitive: a real security-eng deliverable names at least one.
_SCAN_EVIDENCE = re.compile(
    r"\b(scan(?:s|ned|ning)?|red[- ]?team|vuln(?:erabilit(?:y|ies))?|cve|"
    r"finding(?:s)?|sast|dast|gitleaks|owasp|remediat(?:e|ed|ion)|exploit|"
    r"pentest|threat[- ]?model)\b",
    re.IGNORECASE,
)


def input_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    """Shared scope screen + a security-relevance screen."""
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
    """Accept only work that reports scan / red-team finding evidence."""
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
