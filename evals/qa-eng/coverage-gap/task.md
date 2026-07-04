# Golden task — qa-eng — coverage-gap

**Role:** `qa-eng`
**Kind:** deterministic

## Prompt

`fixtures/coverage.json` is a per-function coverage report. List exactly the
functions that are **not** covered by tests.

## Input

- `fixtures/coverage.json` — `{"functions": [{"name": str, "covered": bool}, ...]}`.

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{ "uncovered": ["<function name>", ...] }
```

## Scoring (deterministic, fractional credit)

Credit rewards true positives and penalises false positives, normalised by the
number of genuinely-uncovered functions:

```
credit = clamp01( (|reported ∩ uncovered| - |reported \ uncovered|) / |uncovered| )
```

A blank submission (`uncovered: []` or omitted) scores `0.0`. The uncovered set is
derived from the report inside `verify.py`; it is never spelled out in the prompt.
