# Golden task — product-analyst — kpi-trend

**Role:** `product-analyst`
**Kind:** deterministic

## Prompt

Given the KPI time series in `fixtures/series.json`, decide whether there is a meaningful drift (net change magnitude >= 0.05) and its direction.

## Input

- `fixtures/series.json` — the ordered KPI values.

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{
  "drift_detected": <true|false>,
  "direction": "<name>"
}
```

## Scoring (deterministic, fractional credit)

- `0.5` — `drift_detected` matches `abs(last - first) >= 0.05`.
- `0.5` — `direction` is `down` if the net change is negative, else `up` (only graded when drift is detected).

A blank submission scores `0.0`. The answer key lives only in `verify.py`.
