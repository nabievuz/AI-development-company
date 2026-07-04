# Golden task — support-lead — canned-response-match

**Role:** `support-lead`
**Kind:** deterministic

## Prompt

For each customer message in `fixtures/messages.json`, pick the single best
canned-response template from the catalog in `fixtures/templates.json`
(matching its `use_when` description) that should be sent back to the
customer.

Each message matches exactly one template's `use_when` scenario.

## Input

- `fixtures/templates.json` — the canned-response catalog (id + when to use it).
- `fixtures/messages.json` — 5 customer messages to match.

## Required submission

A JSON object (recorded under `submissions/`) mapping each message id to the
chosen template id:

```json
{
  "answers": {
    "<message-id>": <template-id>, "...": "..."
  }
}
```

## Scoring (deterministic, fractional credit)

- credit = `correct_matches / total_messages`.
- A missing or wrong template id for a message counts as incorrect.

A blank submission scores `0.0`. The answer key lives only in `verify.py`.
