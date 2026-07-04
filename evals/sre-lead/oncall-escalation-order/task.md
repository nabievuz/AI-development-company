# Golden task — sre-lead — oncall-escalation-order

**Role:** `sre-lead`
**Kind:** deterministic

## Prompt

You are the SRE / DevOps Lead triaging the on-call queue: several incidents
are open at once and you must hand the team a single work order. Given the
open incidents in `fixtures/queue.json`, produce the escalation order using
this priority rule (highest priority first):

1. Lower severity number first (`SEV1` before `SEV2` before `SEV3` before
   `SEV4`).
2. Within the same severity, `enterprise` customer tier before `standard`.
3. Within the same severity and tier, the OLDER incident first (higher
   `age_minutes` first).

## Input

- `fixtures/queue.json` — a list of incidents, each with `id`, `severity`
  (`"SEV1"`..`"SEV4"`), `age_minutes`, `customer_tier` (`"enterprise"` or
  `"standard"`).

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{
  "order": ["<incident-id>", "<incident-id>", "<incident-id>", "<incident-id>", "<incident-id>"]
}
```

## Scoring (deterministic, fractional credit)

- credit = fraction of positions that match the expected escalation order
  computed from `fixtures/queue.json`.

A blank submission scores `0.0`. The answer key (sort application) lives
only in `verify.py`.
