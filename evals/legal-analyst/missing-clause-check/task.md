# Golden task — legal-analyst — missing-clause-check

**Role:** `legal-analyst`
**Kind:** deterministic

## Prompt

Review the draft Master Service Agreement in `fixtures/msa.md` against the
standard commercial-contract clause checklist below. List exactly the clause
IDs that are **missing** from the draft (not present anywhere in the
document, in substance).

### Standard clause checklist

| clause ID | what it covers |
|---|---|
| `confidentiality` | non-disclosure of confidential information |
| `governing_law` | choice of law / venue |
| `payment_terms` | invoicing and payment schedule |
| `indemnification` | one party defends/compensates the other for third-party claims |
| `limitation_of_liability` | a cap on damages either party can recover |
| `data_breach_notification` | obligation to notify on a data breach |
| `assignment` | rules on assigning the agreement or subcontracting work |
| `termination` | conditions under which either party may end the agreement |

## Input

- `fixtures/msa.md` — the draft agreement under review.

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{ "missing_clauses": ["<clause ID>", ...] }
```

## Scoring (deterministic, fractional credit)

Credit rewards true positives and penalises false positives, normalised by
the number of genuinely-missing clauses:

```
credit = clamp01( (|reported ∩ missing| - |reported \ missing|) / |missing| )
```

A blank submission (`missing_clauses: []` or omitted) scores `0.0`. Which
clauses from the checklist are actually missing is determined by reading
`fixtures/msa.md`; it is never spelled out in this prompt.
