# Golden task — frontend-eng-1 — ui-state-bug-classification

**Role:** `frontend-eng-1`
**Kind:** deterministic

## Prompt

`fixtures/snippets.json` lists 5 short React hook snippets (`s1`..`s5`). For
each snippet, classify the UI-state bug it exhibits, or say it has none.

Allowed categories:
- `"missing-cleanup"` — an effect starts a subscription/timer/interval and
  never tears it down.
- `"stale-closure"` — an effect (or callback) reads a value from an outer
  scope but that value is missing from the dependency array, so the effect
  keeps acting on a stale snapshot.
- `"race-condition"` — an async handler can resolve out of order (e.g. a
  fast-changing input triggers overlapping requests) and blindly applies
  whichever response lands last, with no guard against a stale response.
- `"ok"` — no state bug; the effect/handler is correctly guarded and cleaned up.

## Input

- `fixtures/snippets.json` — 5 snippets, each with an `id` and `code`.

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{
  "classifications": {
    "s1": "<missing-cleanup|stale-closure|race-condition|ok>",
    "s2": "<missing-cleanup|stale-closure|race-condition|ok>",
    "s3": "<missing-cleanup|stale-closure|race-condition|ok>",
    "s4": "<missing-cleanup|stale-closure|race-condition|ok>",
    "s5": "<missing-cleanup|stale-closure|race-condition|ok>"
  }
}
```

## Scoring (deterministic, fractional credit)

- credit = `correct / total_snippets` (5). The snippet→category answer key
  lives only in `verify.py`, not the fixture.

A blank submission scores `0.0`.
