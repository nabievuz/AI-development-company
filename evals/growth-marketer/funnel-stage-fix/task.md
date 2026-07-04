# Golden task — growth-marketer — funnel-stage-fix

**Role:** `growth-marketer`
**Kind:** deterministic

## Prompt

Given the acquisition funnel in `fixtures/funnel.json` (ordered stages, each with
observed `visitors` and a target `benchmark_rate` for the transition INTO that
stage from the previous one), identify the transition with the largest
absolute gap between its benchmark conversion rate and its actual conversion
rate. This is the stage growth should prioritize fixing first.

Also estimate the **expected lift** in visitors at that stage if the
transition were brought up to its benchmark rate:
`lift = round(prev_stage_visitors * benchmark_rate - actual_stage_visitors)`.

## Input

- `fixtures/funnel.json` — ordered funnel stages with `visitors` and
  `benchmark_rate` per transition.

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{
  "priority_stage": "<stage-name>",
  "expected_lift": <float>
}
```

## Scoring (deterministic, fractional credit)

- `0.5` — `priority_stage` equals the destination stage of the transition with
  the largest `(benchmark_rate - actual_rate)` gap.
- `0.5` — `expected_lift` is within `±5` of the computed lift for that stage.

A blank submission scores `0.0`. The answer key lives only in `verify.py`.
