"""Guardrail for the ``security-lead`` role (example — DAS-1471).

INPUT: reuses the shared scope screen (wrong-dept / missing-consumes /
gate-open), then adds a security-specific refusal: a security-lead ticket must
actually be a security ticket.

OUTPUT: a security sign-off is only accepted when the produced work shows an
explicit sign-off decision AND does not leak a plaintext secret. This is the
discipline's Definition of Done: "the gate you own is explicitly passed or
blocked, with the evidence and the decision recorded" (role overlay).
"""
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

# A security ticket names at least one security concern somewhere in its scope.
_SECURITY_TERMS = re.compile(
    r"\b(security|auth|secret|credential|vuln|cve|owasp|guardrail|red[- ]?team|"
    r"encryption|supply[- ]?chain|compliance)\b",
    re.IGNORECASE,
)

# An explicit sign-off decision the output MUST record.
_SIGNOFF = re.compile(r"\b(sign[- ]?off|signed[- ]?off|approved|risk[- ]accepted|blocked)\b", re.IGNORECASE)

# A crude "leaked plaintext secret" tripwire (example heuristic only).
_LEAKED_SECRET = re.compile(
    r"(?i)(?:password|secret|api[_-]?key|token)\s*[:=]\s*['\"]?[A-Za-z0-9/+=_-]{8,}"
)


def input_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    """Shared scope screen + a security-relevance screen."""
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
    """Security sign-off must be explicit and must not leak a plaintext secret."""
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
