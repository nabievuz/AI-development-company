# Golden task — sre-eng — runbook-gap

**Role:** `sre-eng`
**Kind:** deterministic

## Prompt

The incident runbook in `fixtures/runbook.json` lists the required steps and the steps currently present. Report the steps that are missing.

## Input

- `fixtures/runbook.json` — `required` and `present` step lists.

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{
  "missing_steps": ["<step_name>", "..."]
}
```

## Scoring (deterministic, fractional credit)

- credit = `(hits - false_positives) / |missing set|`, clamped to `[0,1]`. The missing set = `required` minus `present`.

A blank submission scores `0.0`. The answer key lives only in `verify.py`.
