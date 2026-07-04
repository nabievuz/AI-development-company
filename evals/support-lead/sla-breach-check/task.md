# Golden task — support-lead — sla-breach-check

**Role:** `support-lead`
**Kind:** deterministic

## Prompt

Using `fixtures/policy.json` (the first-response SLA policy and the fixed
reference time `now`) and `fixtures/tickets.json` (each ticket's `priority`,
`created_at`, and `first_response_at`), decide whether each ticket's
first-response SLA has been **breached**.

Rules (apply mechanically):

- Each `priority` has a first-response time limit in hours
  (`policy.json.first_response_hours`).
- If `first_response_at` is set, the elapsed time is
  `first_response_at - created_at`.
- If `first_response_at` is `null`, the ticket has not been responded to yet —
  the elapsed time is `now - created_at` (using the fixed `now` in
  `policy.json`).
- A ticket is **breached** (`true`) if its elapsed time is **strictly greater
  than** its priority's limit; otherwise it is not breached (`false`).

## Input

- `fixtures/policy.json` — SLA limits per priority + the fixed `now`.
- `fixtures/tickets.json` — 6 tickets to evaluate.

## Required submission

A JSON object (recorded under `submissions/`) with one boolean per ticket id:

```json
{
  "breaches": {
    "<ticket-id>": <true|false>, "...": "..."
  }
}
```

## Scoring (deterministic, fractional credit)

- credit = `correct_booleans / total_tickets`.
- A missing or non-boolean entry for a ticket counts as incorrect.

A blank submission scores `0.0`. The answer key lives only in `verify.py`.
