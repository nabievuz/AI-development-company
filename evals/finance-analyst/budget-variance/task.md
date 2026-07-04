# Golden task — finance-analyst — budget-variance

**Role:** `finance-analyst`
**Kind:** deterministic

## Prompt

`fixtures/budget.json` is a per-department budget-vs-actual report for one
quarter. Compute each department's budget variance percentage —
`(actual - budget) / budget * 100` — and list exactly the departments that are
**over budget by more than 10%**.

## Input

- `fixtures/budget.json` — `{"period": str, "departments": [{"name": str,
  "budget": number, "actual": number}, ...]}`.

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{ "over_budget": ["<department name>", ...] }
```

## Scoring (deterministic, fractional credit)

Credit rewards true positives and penalises false positives, normalised by the
number of genuinely over-budget (>10% variance) departments:

```
credit = clamp01( (|reported ∩ over_budget| - |reported \ over_budget|) / |over_budget| )
```

The over-budget set is derived from the SAME budget report inside `verify.py` —
it is never spelled out in the prompt. A blank submission
(`over_budget: []` or omitted) scores `0.0`.
