from __future__ import annotations

import re

from guardrails import (
    GuardrailContext,
    GuardrailResult,
    default_input_guardrail,
    ok_result,
    trip,
)

ROLE = "security-lead"


_SECURITY_TERMS = re.compile(
    r"\b(security|auth|secret|credential|vuln|cve|owasp|guardrail|red[- ]?team|"
    r"encryption|supply[- ]?chain|compliance)\b",
    re.IGNORECASE,
)


_SIGNOFF = re.compile(r"\b(sign[- ]?off|signed[- ]?off|approved|risk[- ]accepted|blocked)\b", re.IGNORECASE)


_LEAKED_SECRET = re.compile(
    r"(?i)(?:password|secret|api[_-]?key|token)\s*[:=]\s*['\"]?[A-Za-z0-9/+=_-]{8,}"
)


def input_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    ok, feedback = default_input_guardrail(ctx)
    if not ok:
        return (ok, feedback)
    haystack = f"{ctx.frontmatter.get('title', '')}\n{ctx.body}"
    if not _SECURITY_TERMS.search(haystack):
        return trip(
            "off-scope for security-lead: the ticket names no security concern "
            "(auth/secrets/vuln/guardrail/red-team/…); re-route to the owning "
            "engineering role."
        )
    return ok_result()


def output_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    output = (ctx.output or "").strip()
    if not output:
        return trip("empty output: no security review was produced; re-run the review.")
    if _LEAKED_SECRET.search(output):
        return trip(
            "security violation: output contains what looks like a plaintext "
            "secret (password/api-key/token literal); redact it and record the "
            "credential rotation before sign-off."
        )
    if not _SIGNOFF.search(output):
        return trip(
            "no sign-off recorded: a security review must end in an explicit "
            "decision (signed-off / risk-accepted / blocked) with evidence; the "
            "output records none."
        )
    return ok_result()
