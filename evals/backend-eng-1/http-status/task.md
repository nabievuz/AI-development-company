# Golden task — backend-eng-1 — http-status

**Role:** `backend-eng-1`
**Kind:** deterministic

## Prompt

For each API scenario in `fixtures/scenarios.json`, choose the correct HTTP status code to return.

## Input

- `fixtures/scenarios.json` — scenarios keyed by `id` with a `situation`.

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{
  "statuses": { "<scenario_id>": <int>, "...": "..." }
}
```

## Scoring (deterministic, fractional credit)

- credit = `correct / total_scenarios`. The situation→status mapping is the graded knowledge (it lives in `verify.py`, not the fixture).

A blank submission scores `0.0`. The answer key lives only in `verify.py`.
