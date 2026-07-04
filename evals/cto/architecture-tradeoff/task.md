# Golden task — cto — architecture-tradeoff

**Role:** `cto`
**Kind:** deterministic

## Prompt

`fixtures/cases.json` lists architecture decisions, each with a short list of
candidate options. Apply the following trade-off rule to EVERY case and pick
the winning option:

1. **Security is a hard gate.** Discard any option whose `security_risk` is
   `"high"` — UNLESS every option in the case is `"high"` risk (then risk
   cannot discriminate between them, so fall through to rule 2 using all
   options).
2. Among the remaining candidates, pick the option with the lowest
   `monthly_cost_usd`.
3. If still tied, pick the lowest `latency_ms`.
4. If still tied, pick the option whose `id` sorts first lexicographically.

## Input

- `fixtures/cases.json` — array of
  `{id, description, options: [{id, security_risk, monthly_cost_usd, latency_ms}]}`.

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{ "choices": { "<case id>": "<winning option id>", ... } }
```

## Scoring (deterministic, fractional credit)

The winning option per case is recomputed by applying the rule above to that
case's `fixtures/cases.json` data — the answer is never spelled out in this
prompt. Credit is the fraction of cases matched:

```
credit = (# cases with the correct winning option id) / (# cases)
```

A blank submission (`choices` omitted or empty) scores `0.0`.
