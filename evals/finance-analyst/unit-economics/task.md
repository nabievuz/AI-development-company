# Golden task — finance-analyst — unit-economics

**Role:** `finance-analyst`
**Kind:** deterministic

## Prompt

`fixtures/metrics.json` gives one subscription segment's monthly unit
economics. Compute:

1. **Customer lifetime value (LTV)**, using the standard formula
   `LTV = ARPU * gross_margin / monthly_churn_rate` (rates as decimals, not
   percentages).
2. **LTV:CAC ratio** = `LTV / CAC`.

## Input

- `fixtures/metrics.json` — `{"segment": str, "arpu_monthly_usd": number,
  "gross_margin_pct": number, "monthly_churn_pct": number, "cac_usd": number}`.

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{ "ltv": <number, USD>, "ltv_cac_ratio": <number> }
```

## Scoring (deterministic, fractional credit)

Both `ltv` and `ltv_cac_ratio` are graded independently against the value
`verify.py` derives from the same fixture, with a tolerance band:

- Relative error ≤ 2% → full credit (1.0) for that field.
- Relative error between 2% and 22% → credit decays linearly to 0.0.
- Relative error ≥ 22%, missing, or non-numeric → 0.0 for that field.

The task credit is the mean of the two field credits. A blank/empty submission
scores `0.0`.
