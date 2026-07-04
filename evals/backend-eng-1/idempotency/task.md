# Golden task — backend-eng-1 — idempotency

**Role:** `backend-eng-1`
**Kind:** deterministic

## Prompt

Read the endpoint description in `fixtures/endpoint.md`. Decide whether the endpoint must be idempotent, and name the mechanism that makes retries safe.

## Input

- `fixtures/endpoint.md` — the endpoint description.

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{
  "idempotent": <bool>,
  "mechanism": "<mechanism>"
}
```

## Scoring (deterministic, fractional credit)

- `0.5` — `idempotent` matches what the endpoint requires (a payment/charge/order endpoint must be).
- `0.5` — `mechanism` is an accepted strategy (`idempotency_key` | `dedup_token` | `unique_request_id` | `conditional_put`).

A blank submission scores `0.0`. The answer key lives only in `verify.py`.
