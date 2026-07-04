# Golden task — cto — escalation-routing

**Role:** `cto`
**Kind:** deterministic

## Prompt

`fixtures/scenarios.json` lists engineering decisions that landed on your desk.
For each scenario, decide whether it is **within your charter authority**
(delegate it to the lead who owns that domain) or whether it **exceeds your
charter authority** (escalate to the CEO, per `engineering/agents/cto/AGENTS.md`
"When to escalate" and the `cto → ceo` escalation route in
`governance/communication-flows.yaml`).

## Policy (apply exactly, per scenario)

A scenario **must escalate to `ceo`** if ANY of the following holds:
- `budget_usd > 250000` (spend past your delegated budget authority), OR
- `cross_dept_conflict` is `true` (a cross-department disagreement — flag,
  don't decide unilaterally), OR
- `requires_ceo_approval` is `true` (already flagged as needing sign-off).

Otherwise, **delegate** to the lead owning `domain`:

| domain     | route          |
|------------|----------------|
| `backend`  | `backend-em`   |
| `frontend` | `frontend-em`  |
| `quality`  | `qa-lead`      |
| `security` | `security-lead`|
| `infra`    | `sre-lead`     |

## Input

- `fixtures/scenarios.json` — array of
  `{id, domain, description, budget_usd, cross_dept_conflict, requires_ceo_approval}`.

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{
  "decisions": {
    "<scenario id>": { "action": "delegate" | "escalate", "route": "<lead role or 'ceo'>" },
    ...
  }
}
```

## Scoring (deterministic, fractional credit)

For each scenario, the expected `(action, route)` pair is recomputed from the
policy above applied to that scenario's fields in `fixtures/scenarios.json` —
the expected answer is never spelled out in this prompt. Credit is the fraction
of scenarios where BOTH `action` and `route` match:

```
credit = (# scenarios with correct action AND route) / (# scenarios)
```

A blank submission (`decisions` omitted or empty) scores `0.0`.
