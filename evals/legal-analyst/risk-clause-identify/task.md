# Golden task — legal-analyst — risk-clause-identify

**Role:** `legal-analyst`
**Kind:** deterministic

## Prompt

Review the numbered contract clauses in `fixtures/clauses.txt`. Exactly one
clause carries an unusual, high-risk term for the receiving party (an
uncapped/unlimited liability exposure with no negotiated cap). Identify the
clause number and classify the risk it presents.

## Input

- `fixtures/clauses.txt` — six numbered clauses from a draft agreement.

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{
  "risk_clause": "<clause number as printed in fixtures/clauses.txt>",
  "risk_category": "<one of: liability | unlimited_liability | uncapped_liability | limitation_of_liability>"
}
```

## Scoring (deterministic, fractional credit)

- `0.5` — `risk_clause` is the clause number (as printed in the fixture) that
  carries the high-risk uncapped-liability term.
- `0.5` — `risk_category` is one of `liability` | `unlimited_liability` |
  `uncapped_liability` | `limitation_of_liability`.

A blank submission scores `0.0`. The answer key lives only in `verify.py`.
