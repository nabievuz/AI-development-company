# Golden task — security-eng — secret-in-diff

**Role:** `security-eng`
**Kind:** deterministic

## Prompt

Review the unified diff in `fixtures/change.diff`. Find the added line that commits a hard-coded secret and classify it.

## Input

- `fixtures/change.diff` — the change to review.

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{
  "secret_line": <int>,
  "kind": "<category>"
}
```

## Scoring (deterministic, fractional credit)

- `0.5` — `secret_line` (1-indexed within the diff) is the added line carrying a secret.
- `0.5` — `kind` is one of `api_key` | `secret` | `credential` | `token`.

A blank submission scores `0.0`. The answer key lives only in `verify.py`.
