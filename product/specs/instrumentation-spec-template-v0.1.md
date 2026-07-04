# Instrumentation Spec Template

**Date:** 2026-05-18
**Author:** Product Analyst
**Status:** Approved for use — copy and fill in for each feature

---

## How to use this template

1. Copy this file to `specs/instrumentation-<feature>-v0.1.md`.
2. Fill in every section. Leave nothing as "TBD" when you submit for engineering.
3. Get sign-off from Product Analyst (event schema) and the engineering lead (implementation feasibility) before the sprint starts.
4. Link the spec from the feature spec in `specs/` and from the relevant roadmap row.

---

## Header

| Field | Value |
|-------|-------|
| Feature | _name of the feature being instrumented_ |
| Author | _your name_ |
| Date | _YYYY-MM-DD_ |
| Status | Draft / In Review / Approved / Implemented |
| Feature spec | _link to the feature spec_ |
| Metrics framework | [metrics-framework-v0.1](metrics-framework-v0.1.md) |
| Metrics impacted | _list L1/L2/L3 metrics this instrumentation feeds_ |

---

## 1. Goal

_One paragraph: what product question does this instrumentation answer? Which metric(s) does it move or measure? How does it connect to the north star?_

---

## 2. Events

Repeat the block below for every event. Aim for the minimum number of events that answers the question — avoid vanity events.

---

### Event: `<namespace>.<object>.<action>`

**Naming convention:** `<product>.<object>.<past-tense-verb>`
Examples: `dasflow.task.created`, `dasflow.agent.heartbeat_completed`, `dasflow.workspace.plan_upgraded`

| Field | Value |
|-------|-------|
| Event name | `dasflow.<object>.<action>` |
| Fires when | _describe the exact moment this event fires_ |
| Fired by | Server-side / Client-side / Both |
| Idempotency | _can the same logical action fire this event more than once? how do we deduplicate?_ |
| L1/L2/L3 metric | _which metric(s) in the framework does this feed?_ |

#### Required properties

| Property | Type | Description | Example |
|----------|------|-------------|---------|
| `workspace_id` | string (UUID) | workspace that owns the object | `"a1b2c3d4-..."` |
| `user_id` | string (UUID) \| null | user who triggered the action; null for agent-triggered events | `"u-abc123"` |
| `agent_id` | string (UUID) \| null | agent that triggered the action; null for user-triggered events | `"ag-xyz789"` |
| `timestamp` | ISO 8601 string | server-side event time (UTC) | `"2026-05-18T10:30:00Z"` |
| _add more_ | | | |

#### Optional properties

| Property | Type | Description | Example |
|----------|------|-------------|---------|
| `plan` | string enum | workspace plan at event time | `"free"`, `"starter"`, `"growth"`, `"enterprise"` |
| _add more_ | | | |

#### Sample payload

```json
{
  "event": "dasflow.<object>.<action>",
  "workspace_id": "a1b2c3d4-0000-0000-0000-000000000000",
  "user_id": "u-abc123",
  "agent_id": null,
  "timestamp": "2026-05-18T10:30:00.000Z",
  "plan": "free"
}
```

#### Validation rules

- `workspace_id` must be a valid UUID and must exist in the workspaces table.
- Either `user_id` or `agent_id` must be non-null (not both null).
- `timestamp` must not be more than 60 seconds in the past at ingestion time.
- _add field-specific rules_

---

_(copy the block above for each additional event)_

---

## 3. Funnel / Journey mapping (optional)

_If this feature contributes to a funnel, map the ordered events here._

```
dasflow.workspace.created
  → dasflow.agent.created
    → dasflow.task.created
      → dasflow.task.completed   ← north star
```

Include expected drop-off rates if known.

---

## 4. Dashboard / Query plan

For each metric this spec feeds, describe how the event(s) above roll up into a number.

| Metric | Query sketch |
|--------|-------------|
| _metric name_ | `COUNT(DISTINCT workspace_id) WHERE event = 'dasflow.<x>' AND date BETWEEN ...` |

---

## 5. Implementation notes

| Item | Detail |
|------|--------|
| Delivery guarantee | At-least-once / Exactly-once / Best-effort |
| Backfill required? | Yes (describe) / No |
| PII handling | List any PII fields; confirm they are excluded or hashed before pipeline ingestion |
| Staging validation | Describe how QA will verify events fire correctly before production |
| Rollout | All users / % rollout / feature-flagged |

---

## 6. Sign-off

| Role | Name | Date | Status |
|------|------|------|--------|
| Product Analyst | | | ☐ Approved |
| Engineering lead | | | ☐ Approved |
| Sr. PM (if feature owner) | | | ☐ Approved |

---
