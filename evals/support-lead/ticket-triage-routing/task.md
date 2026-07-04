# Golden task — support-lead — ticket-triage-routing

**Role:** `support-lead`
**Kind:** deterministic

## Prompt

Triage each support ticket in `fixtures/tickets.json`. For every ticket, apply
the routing and priority rubric below **mechanically** (no outside knowledge
needed) and assign exactly one `category`, one `route`, and one `priority`.

### Routing rubric (category → route)

| Category | Signal | Route |
|---|---|---|
| `billing` | charges, invoices, refunds, payments | `billing-team` |
| `bug` | crash, error, broken functionality | `eng-oncall` |
| `how-to` | "how do I", general usage question | `support-tier2` |
| `feature-request` | suggestion / idea for something new | `product` |
| `account-access` | login, password, locked out | `support-tier2` |

### Priority rubric

- `P1` — the customer is **completely blocked**: cannot use the product at
  all (e.g. a crash that prevents login, total account lockout with no
  recovery path).
- `P2` — **partial or financial impact**, but the product is still usable
  (e.g. a billing error, a degraded-but-working feature).
- `P3` — **no blocker**: a general question or an enhancement request.

## Input

- `fixtures/tickets.json` — 5 tickets, each with `id`, `subject`, `body`.

## Required submission

A JSON object (recorded under `submissions/`) with one entry per ticket id:

```json
{
  "triage": {
    "<ticket-id>": {"category": <category>, "route": <queue>, "priority": <P1|P2|P3>}
  }
}
```

## Scoring (deterministic, fractional credit)

- Each ticket has 3 gradable fields (`category`, `route`, `priority`).
- credit = `correct_fields / (3 * number_of_tickets)`.
- A blank/missing entry for a ticket scores 0 on all 3 of its fields.

A blank submission scores `0.0`. The answer key lives only in `verify.py`.
