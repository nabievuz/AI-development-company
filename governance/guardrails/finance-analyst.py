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


_FINANCE_TERMS = re.compile(
    r"\b(budget|burn|cost|costs|spend|spending|invoice|billing|bill|token|"
    r"infra|finance|financial|price|pricing|revenue|forecast|unit[- ]?econ|"
    r"saas|subscription|expense|expenses|usd|cash|margin|quota)\b",
    re.IGNORECASE,
)


_NUMERIC = re.compile(
    r"(?i)(?:"
    r"\$\s?\d|\d+(?:[.,]\d+)?\s?%"
    r"|\b\d[\d,.]*\s?(?:usd|dollars?|eur|gbp|k|m|bn|mo|x)\b"
    r")"
)


def input_guardrail(ctx: GuardrailContext) -> GuardrailResult:
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
