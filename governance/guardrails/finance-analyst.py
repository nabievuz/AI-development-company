"""Guardrail for the ``finance-analyst`` role (R4 — rollout 2->32).

INPUT: the shared scope screen plus a finance-relevance screen — a
finance/billing ticket must actually name a financial concern (budget / burn /
cost / spend / invoice / token or infra spend), mirroring security-lead's
terms screen for its specialist discipline.

OUTPUT: a finance analysis is only accepted when the produced work carries an
actual numeric figure. This encodes the discipline's Definition of Done — "the
analysis is delivered with sourced findings and a clear, actionable
recommendation" over "token/infra budget checks, burn reports — numeric" (role
overlay): a finance finding with no number is not an analysis.
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

ROLE = "finance-analyst"

# A finance ticket names at least one financial concern somewhere in its scope.
_FINANCE_TERMS = re.compile(
    r"\b(budget|burn|cost|costs|spend|spending|invoice|billing|bill|token|"
    r"infra|finance|financial|price|pricing|revenue|forecast|unit[- ]?econ|"
    r"saas|subscription|expense|expenses|usd|cash|margin|quota)\b",
    re.IGNORECASE,
)

# Positive evidence of a numeric metric: a currency amount, a percentage, or any
# bare number. Tolerant on purpose — any real figure satisfies it.
# A METRIC-shaped figure (currency, percentage, or a number next to a money unit)
# — NOT a lone digit, so an incidental ticket id / bare year does not satisfy the
# "must report a figure" gate.
_NUMERIC = re.compile(
    r"(?i)(?:"
    r"\$\s?\d|\d+(?:[.,]\d+)?\s?%"
    r"|\b\d[\d,.]*\s?(?:usd|dollars?|eur|gbp|k|m|bn|mo|x)\b"
    r")"
)


def input_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    """Shared scope screen + a finance-relevance screen."""
    ok, feedback = default_input_guardrail(ctx)
    if not ok:
        return (ok, feedback)
    haystack = f"{ctx.frontmatter.get('title', '')}\n{ctx.body}"
    if not _FINANCE_TERMS.search(haystack):
        return trip(
            "off-scope for finance-analyst: the ticket names no financial concern "
            "(budget/burn/cost/spend/invoice/token or infra spend); re-route to "
            "the owning operations role."
        )
    return ok_result()


def output_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    """Accept only a finance analysis that carries an actual numeric figure."""
    ok, feedback = default_output_guardrail(ctx)
    if not ok:
        return (ok, feedback)
    output = (ctx.output or "").strip()
    if not _NUMERIC.search(output):
        return trip(
            "no numeric metric: a finance / billing analysis must report at least "
            "one figure (a cost, burn rate, percentage, or budget number); the "
            "output shows none — quantify the finding before it can be accepted."
        )
    return ok_result()
