# Golden task — board-member — charter-scope-classify

**Role:** `board-member`
**Kind:** deterministic

## Prompt

`fixtures/charters.json` gives two dept charters (`engineering`, `product`), each
with an `authority` list (decisions that dept owns outright) and an
`out_of_scope` list (decisions that dept must route to another owner). It also
lists `proposals` — each a `dept` + the exact `item` text under review.

As Board Member, classify every proposal:
- If `item` appears in its dept's `authority` list → `"within_authority"`,
  `escalate_to: null`.
- If `item` appears in its dept's `out_of_scope` list → `"escalate"`,
  `escalate_to` = that entry's `owner` (lowercase, exact string from the fixture).

## Input

- `fixtures/charters.json` — `charters` (per-dept `authority` / `out_of_scope`) and
  `proposals` (each an `id`, `dept`, `item`).

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{
  "classifications": {
    "<proposal-id>": {"status": "within_authority" | "escalate", "escalate_to": <owner-string-or-null>},
    ...
  }
}
```

One entry per proposal id in the fixture.

## Scoring (deterministic, fractional credit)

- Each proposal is worth `1 / (number of proposals)`.
- A proposal earns full credit only when BOTH `status` and `escalate_to` match
  the fixture-derived answer (case-insensitive string compare; `null` must match
  `null`). Partial (status-only) match earns no credit for that proposal.

A blank submission scores `0.0`. The answer key lives only in `verify.py`.
