"""Guardrail for the ``product-analyst`` role (DAS-1471).

INPUT: the shared scope screen, then a metrics-relevance screen — a product
analyst ticket must actually name something measurable (a metric / KPI /
analytics / funnel / cohort concern), otherwise it is off-scope and re-routes to
the owning product role.

OUTPUT: an analysis is only accepted when it presents at least one numeric
value. This encodes the discipline's Definition of Done — "Metrics, KPI/goal-
drift reports; numeric errors insidious" (role overlay): a data analysis that
cites no numbers is a qualitative opinion, not a metrics deliverable.
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

ROLE = "product-analyst"

# A product-analyst ticket names at least one measurable / metrics concern.
_METRIC_TERMS = re.compile(
    r"\b(metric|metrics|kpi|kpis|analytic|analytics|instrumentation|funnel|"
    r"conversion|retention|cohort|dashboard|goal[- ]?drift|measurement|measure|"
    r"data|report|reporting|trend|engagement|usage|adoption|churn|revenue|"
    r"rate|number|numeric)\b",
    re.IGNORECASE,
)

# Positive evidence that the analysis carries a numeric value (any digit).
# A METRIC-shaped number (percentage, currency, or a count next to a metric unit)
# — NOT a lone digit, so an incidental ticket id (DAS-1500) or bare year no longer
# satisfies "cite a measured figure".
_NUMERIC = re.compile(
    r"(?i)(?:"
    r"\$\s?\d|\d+(?:[.,]\d+)?\s?%"
    r"|\b\d[\d,.]*\s?(?:x|percent|users?|dau|mau|wau|sessions?|signups?|"
    r"conversions?|installs?|clicks?|pts|bps|k|m|bn)\b"
    r")"
)


def input_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    """Shared scope screen + a metrics-relevance screen."""
    ok, feedback = default_input_guardrail(ctx)
    if not ok:
        return (ok, feedback)
    haystack = f"{ctx.frontmatter.get('title', '')}\n{ctx.body}"
    if not _METRIC_TERMS.search(haystack):
        return trip(
            "off-scope for product-analyst: the ticket names no measurable "
            "concern (metric/KPI/analytics/funnel/cohort/…); re-route to the "
            "owning product role."
        )
    return ok_result()


def output_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    """Accept only an analysis that presents at least one numeric metric."""
    ok, feedback = default_output_guardrail(ctx)
    if not ok:
        return (ok, feedback)
    output = ctx.output or ""
    if not _NUMERIC.search(output):
        return trip(
            "no numeric evidence: a product-analytics deliverable must cite at "
            "least one number (a metric value / rate / count / delta); the "
            "output is purely qualitative — add the measured figures and their "
            "source before it can be accepted."
        )
    return ok_result()
