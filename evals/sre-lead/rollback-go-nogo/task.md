# Golden task — sre-lead — rollback-go-nogo

**Role:** `sre-lead`
**Kind:** deterministic

## Prompt

You are the SRE / DevOps Lead making the reliability trade-off call after a
bad deploy: rollback, roll forward, or hold and watch. Given the deployment
signals in `fixtures/deployments.json`, decide EACH deployment's disposition
using this decision rule, applied top-down (first matching rule wins):

1. **ROLLBACK** — `data_loss_risk == true` (data safety always overrides —
   even an irreversible migration must be rolled back).
2. **FORWARD_FIX** — `migration_irreversible == true` (and not already
   ROLLBACK) — an irreversible schema migration means you cannot safely roll
   the database back, so you fix forward instead.
3. **ROLLBACK** — `error_rate_increase_pct >= 5` OR
   `p99_latency_increase_pct >= 100` (and not already decided above).
4. **MONITOR** — otherwise.

## Input

- `fixtures/deployments.json` — a list of deployments, each with `id`,
  `data_loss_risk`, `migration_irreversible`, `error_rate_increase_pct`,
  `p99_latency_increase_pct`.

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{
  "decisions": {
    "<deploy-id>": <ROLLBACK|FORWARD_FIX|MONITOR>, "...": "..."
  }
}
```

## Scoring (deterministic, fractional credit)

- credit = fraction of deployments whose reported decision matches the rule
  applied to `fixtures/deployments.json`.

A blank submission scores `0.0`. The answer key (rule application) lives only
in `verify.py`.
