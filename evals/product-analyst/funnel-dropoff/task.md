# Golden task — product-analyst — funnel-dropoff

**Role:** `product-analyst`
**Kind:** deterministic

## Prompt

Given the conversion funnel in `fixtures/funnel.json`, identify the step with the largest RELATIVE drop-off from the previous step (the destination step name).

## Input

- `fixtures/funnel.json` — ordered funnel steps with counts.

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{
  "biggest_dropoff_step": "<name>"
}
```

## Scoring (deterministic, fractional credit)

- `1.0` if `biggest_dropoff_step` equals the step whose relative loss `(prev - cur) / prev` is largest; else `0.0`.

A blank submission scores `0.0`. The answer key lives only in `verify.py`.
