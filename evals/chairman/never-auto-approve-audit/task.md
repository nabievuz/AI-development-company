# Golden task — chairman — never-auto-approve-audit

**Role:** `chairman`
**Kind:** deterministic

## Prompt

You are auditing a batch of tickets (`fixtures/tickets.json`) for a QONUN-5
never-auto-approve violation — the same fail-closed floor enforced in code by
`scripts/check_never_auto_approve.py`. The floor categories that must NEVER be
auto-approved are:

```
new_goal, security_sensitive, schema_migration, gate5_deployment,
governance_or_policy, permission_change, secret_change
```

A ticket is a **violation** when BOTH of these hold:
1. its `approval` field starts with `"auto"`, AND
2. its `ticket_type` is one of the floor categories above, OR one of its
   `labels` is one of the floor categories above.

Review every ticket in `fixtures/tickets.json` and report the `id`s of the
ones that are violations — these are the ones you must block from ratification
and send back for manual sign-off.

## Input

- `fixtures/tickets.json` — the batch of candidate tickets under audit.

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{
  "violations": ["DAS-<id>", "..."]
}
```

List every ticket `id` from `fixtures/tickets.json` that meets both violation
conditions above; the list may be any length from zero to the full batch.

## Scoring (deterministic, fractional credit)

- credit = `(hits - false_positives) / |required violation set|`, clamped to
  `[0, 1]`.

A blank submission scores `0.0`. The answer key lives only in `verify.py`.
