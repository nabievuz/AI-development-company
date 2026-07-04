# Golden task — cpo — feature-tradeoff-risk-budget

**Role:** `cpo`
**Kind:** deterministic

## Prompt

`fixtures/initiatives.json` lists candidate initiatives for next quarter, each
with a cost, an expected value (revenue/retention impact in USD), and a risk
tier (`"low"` or `"high"`). You have a fixed budget (`budget_usd`) and a hard
risk-appetite constraint (`max_high_risk`): the org will not greenlight more
than `max_high_risk` "high" risk initiatives in one quarter, regardless of
their expected value.

Decide which initiatives to greenlight this quarter to **maximize total
expected value** while respecting BOTH constraints:

1. total `cost_usd` of greenlit initiatives <= `budget_usd`
2. count of greenlit initiatives with `risk_tier == "high"` <= `max_high_risk`

This is the trade-off judgment a CPO owns: the naive highest-value picks are
often disqualified by the risk cap, forcing a genuine trade-off, not just a
sort.

## Input

- `fixtures/initiatives.json` — `{"budget_usd": int, "max_high_risk": int, "initiatives": [{"name": str, "cost_usd": int, "expected_value_usd": int, "risk_tier": "low"|"high"}, ...]}`.

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{ "greenlit": ["<initiative name>", ...] }
```

## Scoring (deterministic, fractional credit)

`verify.py` brute-forces every subset (small `n`) to find the maximum total
`expected_value_usd` achievable within both the budget and the high-risk cap
— call this `optimal_value`.

- If the submission violates the budget OR the high-risk cap, credit is `0.0`.
- Otherwise, `achieved_value` = sum of `expected_value_usd` for the greenlit
  initiatives, and `credit = clamp01(achieved_value / optimal_value)`.

A blank submission (`greenlit: []` or omitted) scores `0.0`. The optimal set
is never spelled out in the prompt or fixtures — only in `verify.py`.
