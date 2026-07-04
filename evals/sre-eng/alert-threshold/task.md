# Golden task — sre-eng — alert-threshold

**Role:** `sre-eng`
**Kind:** deterministic

## Prompt

Given the SLO in `fixtures/slo.json`, compute the error budget as a percentage and the allowed downtime in minutes over the window.

## Input

- `fixtures/slo.json` — availability target and window.

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{
  "error_budget_pct": "<float: 100 - availability_target_pct>",
  "downtime_minutes": "<float: window_days * 24 * 60 * error_budget_pct / 100>"
}
```

## Scoring (deterministic, fractional credit)

- `0.5` — `error_budget_pct` equals `100 - availability_target_pct` (tolerance 1e-6).
- `0.5` — `downtime_minutes` equals `window_days * 24 * 60 * error_budget_pct / 100` (tolerance 1e-3).

A blank submission scores `0.0`. The answer key lives only in `verify.py`.
