# Golden task — chairman — precedence-adjudication

**Role:** `chairman`
**Kind:** deterministic

## Prompt

Per `AGENTS.md` §2 ("Precedence (binding)"), the org's document precedence
order (lower number = higher precedence, and wins a direct conflict) is given
in `fixtures/scenarios.json` under `precedence_order`, along with the binding
rule text.

Adjudicate each of the four conflict `scenarios` in `fixtures/scenarios.json`:
for each one, decide which of the two named documents governs, and report the
**precedence-order level number** (1-6) of the WINNING document.

## Input

- `fixtures/scenarios.json` — the precedence order, the rule, and four
  conflict scenarios (`S1`-`S4`).

## Required submission

A JSON object (recorded under `submissions/`) with one winning level number
per scenario, **in scenario order** (`S1`, `S2`, `S3`, `S4`):

```json
{
  "answers": [<priority-int>, <priority-int>, <priority-int>, <priority-int>]
}
```

Each `<priority-int>` is the winning document's precedence-order level
number (1-6) for the corresponding scenario, in `S1..S4` order.

## Scoring (deterministic, fractional credit)

- credit = `(number of scenarios answered with the correct winning level) /
  4`, clamped to `[0, 1]`. Positional: `answers[0]` is judged against `S1`,
  `answers[1]` against `S2`, etc.

A blank submission scores `0.0`. The answer key lives only in `verify.py`.
