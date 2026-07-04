# Golden task — backend-em — escalate-or-delegate

**Role:** `backend-em`
**Kind:** deterministic

## Prompt

Read the three scenarios in `fixtures/scenarios.md`. For each one, decide
whether the Backend EM should **delegate** it to an engineer
(`backend-eng-1` or `backend-eng-2`) or **escalate** it to the CTO, per the
"When to escalate" rules in the role overlay. This exercises the core
backend-em competency of **escalation-vs-delegate judgment**.

## Input

- `fixtures/scenarios.md` — the three scenarios and the delegate/escalate
  rule of thumb.

## Required submission

A JSON object (recorded under `submissions/`) with one entry per scenario:

```json
{
  "decisions": [
    {"scenario": <int>, "action": "<delegate|escalate>", "target": "<backend-eng-1|backend-eng-2|cto>"},
    ...
  ]
}
```

- `action` — one of `"delegate"` | `"escalate"`.
- `target` — for `"delegate"`, either `"backend-eng-1"` or
  `"backend-eng-2"`; for `"escalate"`, `"cto"`.

## Scoring (deterministic, fractional credit)

Per scenario (averaged over the 3 scenarios):

- `0.7` — `action` matches the expected call (scenario 2 exceeds charter
  authority via cross-dept legal/retention risk and an irreversible action
  with no rollback plan → `escalate`; scenarios 1 and 3 are normal in-scope
  engineering work → `delegate`).
- `0.3` (only earned when `action` is correct) — `target` is a valid choice
  for that action (`cto` for escalate; either backend engineer for
  delegate).

A blank/missing `decisions` list scores `0.0`. The answer key lives only in
`verify.py`.
