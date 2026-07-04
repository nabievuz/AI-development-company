# Golden task — product-analyst — ab-significance

**Role:** `product-analyst`
**Kind:** deterministic

## Prompt

Given the A/B test results in `fixtures/experiment.json`, decide whether the difference is statistically significant at p < 0.05 (two-proportion z-test, |z| > 1.96) and name the winning arm.

## Input

- `fixtures/experiment.json` — control/variant `n` and `conversions`.

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{
  "significant": <true|false>,
  "winner": "<name>"
}
```

## Scoring (deterministic, fractional credit)

- `0.5` — `significant` matches the two-proportion z-test outcome.
- `0.5` — `winner` is the arm with the higher conversion rate.

A blank submission scores `0.0`. The answer key lives only in `verify.py`.
