# Golden task — backend-eng-2 — race-condition

**Role:** `backend-eng-2`
**Kind:** deterministic

## Prompt

Review the data-access code in `fixtures/snippet.py`. Decide whether it contains a check-then-act race condition (TOCTOU: read a value, branch on it, then write, with no synchronization between the read and the write) and name a valid fix strategy.

## Input

- `fixtures/snippet.py` — the code under review.

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{
  "has_race_condition": <bool>,
  "fix": "<strategy>"
}
```

## Scoring (deterministic, fractional credit)

- `0.5` — `has_race_condition` matches the pattern actually present in the code.
- `0.5` — `fix` is an accepted strategy (`lock` | `mutex` | `transaction` | `select_for_update` | `optimistic_locking` | `compare_and_swap` | `unique_constraint`).

A blank submission scores `0.0`. The answer key lives only in `verify.py`.
