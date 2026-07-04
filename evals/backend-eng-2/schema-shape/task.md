# Golden task — backend-eng-2 — schema-shape

**Role:** `backend-eng-2`
**Kind:** deterministic

## Prompt

Given the API contract and a set of recorded responses in `fixtures/contract.json`, decide for each response whether its body conforms to the contract's `schema` (every schema field present with the correct type; extra fields are allowed).

## Input

- `fixtures/contract.json` — `schema` (field name → type name) plus `responses` (each with an `id` and a `body`).

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{
  "valid": { "<response_id>": <bool>, "...": "..." }
}
```

## Scoring (deterministic, fractional credit)

- credit = `correct / total_responses`, where "correct" means the submitted verdict for a response id matches whether that response's body actually conforms to `schema`.

A blank submission scores `0.0`. The answer key (the type-matching logic) lives only in `verify.py`.
