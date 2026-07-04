# Golden task — sre-eng — rollback-order

**Role:** `sre-eng`
**Kind:** deterministic

## Prompt

Given the forward deploy steps in `fixtures/deploy.json`, produce the correct rollback sequence (reverse order).

## Input

- `fixtures/deploy.json` — the ordered forward deploy steps.

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{
  "rollback_sequence": ["<step_name>", "..."]
}
```

## Scoring (deterministic, fractional credit)

- credit = fraction of positions that match the reversed forward order.

A blank submission scores `0.0`. The answer key lives only in `verify.py`.
