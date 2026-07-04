# Golden task — content-lead — content-plan-priority

**Role:** `content-lead`
**Kind:** deterministic

## Prompt

The content backlog (`fixtures/backlog.json`) lists candidate content pieces,
each scored 1-5 on `impact`, `urgency`, and `effort`. Prioritize the backlog
for next sprint using the team's standard scoring formula:

```
priority_score = 2 * impact + 1.5 * urgency - 1 * effort
```

Rank every item from **highest** priority_score to **lowest** and return the
ordered list of item `id`s (highest priority first).

## Input

- `fixtures/backlog.json` — the candidate content items with their `id`,
  `impact`, `urgency`, and `effort` scores.

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{
  "order": [<string>, ...]   // item ids, highest priority first
}
```

## Scoring (deterministic, fractional credit)

- The verifier recomputes each item's `priority_score` from the formula above
  and derives the required descending order.
- credit = fraction of **concordant pairs**: for every pair of items where the
  required order ranks item A above item B, the submission earns that pair
  only if both A and B are present in `order` and A appears before B.
  `credit = concordant_pairs / total_pairs`, clamped to `[0,1]`.

A blank, missing, or non-list `order` scores `0.0`. The answer key (the
computed scores and ranking) lives only in `verify.py`.
