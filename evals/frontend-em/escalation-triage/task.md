# Golden task — frontend-em — escalation-triage

**Role:** `frontend-em`
**Kind:** deterministic

## Prompt

You are triaging this week's frontend decision queue in
`fixtures/decisions.json` against your role's escalation policy (per
`engineering/agents/frontend-em/AGENTS.md`, "When to escalate"):

- the decision **exceeds your charter authority** (`exceeds_charter_authority`),
- it has **cross-department impact** (`cross_dept_impact`), or
- it has been **stuck for more than one wave with no progress**
  (`blocked_waves > 1`).

Any decision matching **at least one** of those three conditions must be
escalated to the CTO rather than decided within the frontend team. A decision
matching none of them is squarely within your charter and should be decided
locally, not escalated.

## Input

- `fixtures/decisions.json` — `{"decisions": [{"id": str, "cross_dept_impact": bool, "exceeds_charter_authority": bool, "blocked_waves": int}, ...]}`.

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{ "escalate": ["<decision id>", ...] }
```

## Scoring (deterministic, fractional credit)

Credit rewards true positives and penalises false positives, normalised by the
number of genuinely-escalation-worthy decisions:

```
credit = clamp01( (|reported ∩ escalate_set| - |reported \ escalate_set|) / |escalate_set| )
```

A blank submission (`escalate: []` or omitted) scores `0.0`. The escalate set is
derived from the report inside `verify.py`; the exact answer is never spelled
out in the prompt.
