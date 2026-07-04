# Golden task — ceo — goal-queue-triage

**Role:** `ceo`
**Kind:** deterministic

## Prompt

`fixtures/goal_queue.json` lists six candidate goals awaiting a queue
decision, per the **QONUN — Founder-Approved Goal Queue** law: a new project
or unclear product goal does NOT become board tickets until the Founder
discovery gate clears.

For each goal, decide whether it is **`"approved"`** for board tickets or
**`"blocked"`** pending the Founder, applying this concrete rule:

- The **discovery-questions condition** is satisfied when
  `founder_questions_answered >= 10` **OR** `founder_waived_questions` is
  `true` (the Founder explicitly declined/waived them).
- The **approval-signal condition** is satisfied when `founder_signal` is a
  non-null string containing `"APPROVED"` or `"TASDIQLANDI"`.
- A goal is **`"approved"`** only when **both** conditions are satisfied.
  Otherwise it is **`"blocked"`**.

## Input

- `fixtures/goal_queue.json` — `{"goals": [{"id": str, "title": str,
  "founder_questions_answered": int, "founder_waived_questions": bool,
  "founder_signal": str | null}, ...]}`.

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{ "decisions": { "<id>": "approved" | "blocked", ... } }
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
