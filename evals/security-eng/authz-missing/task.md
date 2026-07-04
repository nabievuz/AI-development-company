# Golden task — security-eng — authz-missing

**Role:** `security-eng`
**Kind:** deterministic

## Prompt

Review the route table in `fixtures/routes.json`. Report the routes that are missing authorization (not `auth: true`) and are NOT intentionally public.

## Input

- `fixtures/routes.json` — route handlers with `auth` and `public` flags.

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{
  "unprotected": [<id>, ...]
}
```

## Scoring (deterministic, fractional credit)

- credit = `(hits - false_positives) / |unprotected set|`, clamped to `[0,1]`. The unprotected set = routes with `auth == false` and `public != true`.

A blank submission scores `0.0`. The answer key lives only in `verify.py`.
