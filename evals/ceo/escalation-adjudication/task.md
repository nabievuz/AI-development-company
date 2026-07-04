# Golden task — ceo — escalation-adjudication

**Role:** `ceo`
**Kind:** deterministic

## Prompt

`fixtures/escalations.json` lists six pending decisions. For each one, decide
whether the **CEO can decide within charter authority** (`"decide"`) or the
decision **must be escalated to the Chairman of the Board** (`"escalate"`),
per the CEO's binding escalation rule (AGENTS.md §6 / `ceo` role overlay):

> A decision above your charter authority is escalated, never decided
> unilaterally; a cross-dept impact is flagged, not decided alone.

Apply this concrete rule to every record:

- **Escalate** if `budget_usd` is **strictly greater than** `charter_limit_usd`,
  **OR** if the decision is both `cross_dept: true` **AND** `reversible: false`
  (an irreversible cross-departmental commitment is always above charter
  authority, regardless of budget).
- **Otherwise, decide** — it is within charter authority.

A budget exactly equal to the charter limit is still within authority (only
budgets that *exceed* the limit escalate).

## Input

- `fixtures/escalations.json` — `{"escalations": [{"id": str, "title": str,
  "budget_usd": number, "charter_limit_usd": number, "cross_dept": bool,
  "reversible": bool}, ...]}`.

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{ "decisions": { "<id>": "decide" | "escalate", ... } }
```

One entry per `id` in the fixture.

## Scoring (deterministic, fractional credit)

```
credit = (# ids classified correctly) / (total # ids)
```

The correct classification for each `id` is derived by `verify.py` by
re-applying the rule above to the fixture — it is never spelled out
per-record in this prompt. A blank submission (`decisions: {}` or omitted)
scores `0.0`.
