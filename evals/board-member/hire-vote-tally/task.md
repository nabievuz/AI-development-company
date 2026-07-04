# Golden task — board-member — hire-vote-tally

**Role:** `board-member`
**Kind:** deterministic

## Prompt

`fixtures/hires.json` lists open agent-hire requests with the votes cast so far,
plus the Governance Charter decision rule that governs hires:

> Hires: any single Board member may approve; only Board may reject.

For each request in `requests`, determine its tally status using ONLY votes cast
by a role listed in `board_roles` (`chairman`, `board-member`) — a vote from any
other role (e.g. `ceo`) does not count toward a hire decision under this rule.

Apply these tie-break semantics:
- **approved** — at least one counting `approve` vote, and no counting `reject` vote.
- **rejected** — at least one counting `reject` vote (a Board reject is decisive,
  regardless of any approvals also present).
- **pending** — no counting vote either way (empty votes, or only non-Board votes).

## Input

- `fixtures/hires.json` — `board_roles`, and `requests` (each an `id` + `votes` list).

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{
  "decisions": {
    "<request-id>": "approved" | "rejected" | "pending",
    ...
  }
}
```

One entry per request id in the fixture.

## Scoring (deterministic, fractional credit)

- credit = (number of request ids scored correctly) / (total requests in the fixture).
- Status strings are matched case-insensitively; an id missing from the
  submission counts as incorrect for that request.

A blank submission scores `0.0`. The answer key lives only in `verify.py`.
