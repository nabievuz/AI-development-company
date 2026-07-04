# Golden task — backend-eng-2 — diagnose-500

**Role:** `backend-eng-2`
**Kind:** deterministic

## Prompt

Read the incident report in `fixtures/incident.md`. Diagnose the root-cause category of the 500 error and name the fix category that would prevent recurrence.

## Input

- `fixtures/incident.md` — a stack trace plus surrounding context.

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{
  "root_cause": "<category>",
  "fix": "<strategy>"
}
```

## Scoring (deterministic, fractional credit)

- `0.5` — `root_cause` matches the category implied by the trace (`null_reference` | `race_condition` | `deadlock` | `timeout` | `unknown`).
- `0.5` — `fix` is an accepted strategy (`null_check` | `guard_clause` | `none_check` | `defensive_check`).

A blank submission scores `0.0`. The answer key lives only in `verify.py`.
