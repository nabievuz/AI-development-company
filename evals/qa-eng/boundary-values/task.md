# Golden task — qa-eng — boundary-values

**Role:** `qa-eng`
**Kind:** deterministic

## Prompt

The function `clamp(x, lo, hi)` described in `fixtures/spec.json` needs boundary tests. List the boundary input values that exercise the edges of its valid range.

## Input

- `fixtures/spec.json` — the function spec with its `lo`/`hi` bounds.

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{
  "cases": [<int>, ...]   // boundary input values to test
}
```

## Scoring (deterministic, fractional credit)

- credit = `(hits - false_positives) / |required boundary set|`, clamped to `[0,1]`. The required set is `{lo-1, lo, hi, hi+1}` derived from the spec — off-by-one edges plus the exact bounds.

A blank submission scores `0.0`. The answer key lives only in `verify.py`.
