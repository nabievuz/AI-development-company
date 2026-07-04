# Golden task — backend-eng-1 — n-plus-one

**Role:** `backend-eng-1`
**Kind:** deterministic

## Prompt

Review the data-access code in `fixtures/snippet.py`. Decide whether it contains an N+1 query pattern (a query issued inside a loop) and name a valid fix strategy.

## Input

- `fixtures/snippet.py` — the code under review.

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{
  "has_n_plus_one": <bool>,
  "fix": "<fix_strategy>"
}
```

## Scoring (deterministic, fractional credit)

- `0.5` — `has_n_plus_one` matches the pattern actually present in the code.
- `0.5` — `fix` is an accepted strategy (`eager_load` | `join` | `prefetch` | `select_related` | `in_query` | `batch`).

A blank submission scores `0.0`. The answer key lives only in `verify.py`.
