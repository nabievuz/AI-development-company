# Golden task — sre-lead — incident-severity-triage

**Role:** `sre-lead`
**Kind:** deterministic

## Prompt

You are the SRE / DevOps Lead classifying concurrent incidents by severity so
the org escalates the right ones first. Given the incident signals in
`fixtures/incidents.json`, classify EACH incident's severity using this policy,
applied top-down (first matching rule wins):

1. **SEV1** — `data_loss == true`, OR (`revenue_impacting == true` AND
   `error_rate_pct >= 50`).
2. **SEV2** — `revenue_impacting == true` AND `error_rate_pct >= 5` (and not
   already SEV1).
3. **SEV3** — `error_rate_pct >= 1` (and not already SEV1/SEV2).
4. **SEV4** — otherwise.

## Input

- `fixtures/incidents.json` — a list of incidents, each with `id`,
  `error_rate_pct`, `affected_users_pct`, `revenue_impacting`, `data_loss`.

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{
  "severities": {
    "<incident-id>": <SEV1|SEV2|SEV3|SEV4>, "...": "..."
  }
}
```

## Scoring (deterministic, fractional credit)

- credit = fraction of incidents whose reported severity matches the policy
  applied to `fixtures/incidents.json`.

A blank submission scores `0.0`. The answer key (policy application) lives
only in `verify.py`.
