"""Guardrail for the ``seo-specialist`` role (marketing — DAS-1471).

INPUT: reuses the shared scope screen (wrong-dept / missing-consumes /
gate-open), then adds an SEO-relevance refusal: an seo-specialist ticket must
actually name a search / SEO concern (analogous to security-lead's terms
screen).

OUTPUT: an SEO deliverable is only accepted when the produced work references a
concrete SEO artifact (keywords / meta title / meta description / structured
data / canonical / sitemap …). This encodes the discipline's routine output
(meta / keyword / structured output): a page that "looks nice" with no SEO
artifact touched is not done.
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

ROLE = "seo-specialist"

# An SEO ticket names at least one search / SEO concern somewhere in its scope.
_SEO_TERMS = re.compile(
    r"\b(seo|search|keywords?|meta|serps?|ranking|rankings?|backlinks?|sitemap|"
    r"schema|structured[- ]?data|canonical|index(?:ing)?|crawl|organic|"
    r"title[- ]?tag|slug|robots|open[- ]?graph)\b",
    re.IGNORECASE,
)

# Positive evidence that a concrete SEO artifact was produced.
_SEO_ARTIFACT = re.compile(
    r"\b(seo|keywords?|meta[- ]?title|meta[- ]?description|meta[- ]?tags?|"
    r"title[- ]?tag|meta|serps?|schema|structured[- ]?data|json[- ]?ld|"
    r"canonical|sitemap|slug|alt[- ]?text|backlinks?|search[- ]?volume|"
    r"ranking|rankings?|open[- ]?graph|robots)\b",
    re.IGNORECASE,
)


def input_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    """Shared scope screen + an SEO-relevance screen."""
    ok, feedback = default_input_guardrail(ctx)
    if not ok:
        return (ok, feedback)
    haystack = f"{ctx.frontmatter.get('title', '')}\n{ctx.body}"
    if not _SEO_TERMS.search(haystack):
        return trip(
            "off-scope for seo-specialist: the ticket names no search / SEO "
            "concern (keyword/meta/schema/ranking/sitemap/…); re-route to the "
            "owning marketing role."
        )
    return ok_result()


def output_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    """Accept only SEO work that references a concrete SEO artifact."""
    ok, feedback = default_output_guardrail(ctx)
    if not ok:
        return (ok, feedback)
    output = (ctx.output or "").strip()
    if not _SEO_ARTIFACT.search(output):
        return trip(
            "no SEO artifact: an SEO deliverable must reference the artifact it "
            "touched (keywords / meta title / meta description / structured data "
            "/ canonical / sitemap …); the output references none — do the SEO "
            "work and cite the artifact."
        )
    return ok_result()
