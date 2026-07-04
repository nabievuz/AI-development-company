# Instrumentation Spec — DasFlow MVP

**Date:** 2026-05-18
**Author:** Product Analyst
**Status:** Draft — pending Engineering lead review
**Feature spec:** [mvp-brief-v0.1](mvp-brief-v0.1.md)
**Metrics framework:** [metrics-framework-v0.1](metrics-framework-v0.1.md)
**Metrics impacted:** All L1 and L2 metrics; L3 feature-level metrics for all 5 MVP features

---

## 1. Goal

Instrument DasFlow MVP's five core features so the team can answer, within 60 days of launch:

1. Are workspaces reaching the north star (≥ 3 completed tasks/week)?
2. Where does the activation funnel break (signup → agent → task → done)?
3. Which workspaces are at risk of churning before week 4?
4. Who is hitting the budget cap, and are they upsell candidates?

All events listed below feed directly into those questions. No vanity events are included.

---

## 2. Events

### Funnel overview

```
dasflow.workspace.created
  → dasflow.agent.created
    → dasflow.task.created
      → dasflow.heartbeat.run
        → dasflow.task.completed   ← North Star
          (optionally) → dasflow.workspace.plan_upgraded
```

---

### Event: `dasflow.workspace.created`

| Field | Value |
|-------|-------|
| Event name | `dasflow.workspace.created` |
| Fires when | A new workspace is persisted and activated after signup |
| Fired by | Server-side |
| Idempotency | Once per workspace; deduplicate on `workspace_id` |
| Metrics fed | Signups (30-day), activation funnel step 1 |

#### Required properties

| Property | Type | Description | Example |
|----------|------|-------------|---------|
| `workspace_id` | string (UUID) | new workspace id | `"ws-abc123"` |
| `user_id` | string (UUID) | user who created the workspace | `"u-xyz789"` |
| `agent_id` | null | always null — user action | `null` |
| `timestamp` | ISO 8601 | server-side creation time (UTC) | `"2026-06-15T09:00:00Z"` |
| `plan` | string enum | plan at creation time | `"free"` |

#### Optional properties

| Property | Type | Description | Example |
|----------|------|-------------|---------|
| `referrer_source` | string | UTM source or channel slug | `"codecanyon"`, `"organic"` |
| `referrer_campaign` | string | UTM campaign | `"q3-launch"` |

#### Sample payload

```json
{
  "event": "dasflow.workspace.created",
  "workspace_id": "ws-abc123-0000-0000-0000-000000000000",
  "user_id": "u-xyz789-0000-0000-0000-000000000000",
  "agent_id": null,
  "timestamp": "2026-06-15T09:00:00.000Z",
  "plan": "free",
  "referrer_source": "organic"
}
```

#### Validation rules

- `workspace_id` must be a valid UUID and must exist in workspaces table.
- `user_id` must be non-null (workspace creation is always user-initiated).
- `plan` must be one of: `free`, `starter`, `growth`, `enterprise`.

---

### Event: `dasflow.agent.created`

| Field | Value |
|-------|-------|
| Event name | `dasflow.agent.created` |
| Fires when | An agent record is persisted in the roster |
| Fired by | Server-side |
| Idempotency | Once per agent; deduplicate on `agent_id` |
| Metrics fed | Day-0 agent creation rate (L2 activation), L3 agents-per-workspace |

#### Required properties

| Property | Type | Description | Example |
|----------|------|-------------|---------|
| `workspace_id` | string (UUID) | owning workspace | `"ws-abc123"` |
| `user_id` | string (UUID) | user who created the agent | `"u-xyz789"` |
| `agent_id` | string (UUID) | new agent id | `"ag-001"` |
| `timestamp` | ISO 8601 | UTC | `"2026-06-15T09:05:00Z"` |
| `plan` | string enum | workspace plan at event time | `"free"` |
| `model` | string | LLM model assigned to agent | `"claude-sonnet-4-6"` |
| `role_template` | string \| null | template used if any | `"engineer"`, `null` |

#### Sample payload

```json
{
  "event": "dasflow.agent.created",
  "workspace_id": "ws-abc123-0000-0000-0000-000000000000",
  "user_id": "u-xyz789-0000-0000-0000-000000000000",
  "agent_id": "ag-001-0000-0000-0000-000000000000",
  "timestamp": "2026-06-15T09:05:00.000Z",
  "plan": "free",
  "model": "claude-sonnet-4-6",
  "role_template": "engineer"
}
```

#### Validation rules

- `agent_id` must be unique; reject duplicate events with 409 at ingest.
- `model` must be a non-empty string matching a known model slug.

---

### Event: `dasflow.task.created`

| Field | Value |
|-------|-------|
| Event name | `dasflow.task.created` |
| Fires when | A task/issue is persisted with any initial status |
| Fired by | Server-side |
| Idempotency | Once per task; deduplicate on `task_id` |
| Metrics fed | Tasks created/workspace/week (L3 upstream driver), activation funnel step 3 |

#### Required properties

| Property | Type | Description | Example |
|----------|------|-------------|---------|
| `workspace_id` | string (UUID) | owning workspace | `"ws-abc123"` |
| `user_id` | string (UUID) \| null | user who created the task; null if agent-created | `"u-xyz789"` |
| `agent_id` | string (UUID) \| null | agent that created the task; null if user-created | `null` |
| `task_id` | string (UUID) | new task id | `"task-001"` |
| `assignee_agent_id` | string (UUID) \| null | agent assigned at creation | `"ag-001"` |
| `timestamp` | ISO 8601 | UTC | `"2026-06-15T09:10:00Z"` |
| `plan` | string enum | workspace plan | `"free"` |

#### Sample payload

```json
{
  "event": "dasflow.task.created",
  "workspace_id": "ws-abc123-0000-0000-0000-000000000000",
  "user_id": "u-xyz789-0000-0000-0000-000000000000",
  "agent_id": null,
  "task_id": "task-001-0000-0000-0000-000000000000",
  "assignee_agent_id": "ag-001-0000-0000-0000-000000000000",
  "timestamp": "2026-06-15T09:10:00.000Z",
  "plan": "free"
}
```

#### Validation rules

- Exactly one of `user_id` or `agent_id` must be non-null.
- `task_id` must be unique across the workspace.

---

### Event: `dasflow.heartbeat.run`

| Field | Value |
|-------|-------|
| Event name | `dasflow.heartbeat.run` |
| Fires when | A heartbeat execution completes (success or failure) |
| Fired by | Server-side |
| Idempotency | Once per heartbeat run id; deduplicate on `run_id` |
| Metrics fed | Heartbeats/agent/day (L3 utilization), guardrail: heartbeat success rate |

#### Required properties

| Property | Type | Description | Example |
|----------|------|-------------|---------|
| `workspace_id` | string (UUID) | owning workspace | `"ws-abc123"` |
| `user_id` | null | always null — agent action | `null` |
| `agent_id` | string (UUID) | agent that ran | `"ag-001"` |
| `run_id` | string (UUID) | heartbeat run id | `"run-007"` |
| `task_id` | string (UUID) \| null | task checked out during this run, if any | `"task-001"` |
| `outcome` | string enum | result of the run | `"success"`, `"error"`, `"no_work"` |
| `duration_ms` | integer | wall-clock time of the run | `4230` |
| `llm_cost_usd` | float | estimated LLM cost for this run | `0.03` |
| `timestamp` | ISO 8601 | run completion time UTC | `"2026-06-15T09:15:00Z"` |
| `plan` | string enum | workspace plan | `"free"` |

#### Validation rules

- `outcome` must be one of: `success`, `error`, `no_work`.
- `duration_ms` must be ≥ 0.
- `llm_cost_usd` must be ≥ 0. Flag runs where `llm_cost_usd > 0.10` for guardrail monitoring.

---

### Event: `dasflow.task.completed`

| Field | Value |
|-------|-------|
| Event name | `dasflow.task.completed` |
| Fires when | A task transitions to `done` status |
| Fired by | Server-side |
| Idempotency | Once per task; if a task moves done → reopened → done again, fire again with `reopen_count > 0` |
| Metrics fed | **North star** (tasks completed/active workspace/week), task completion rate (L3), time-to-first-completed-task (L2 activation) |

#### Required properties

| Property | Type | Description | Example |
|----------|------|-------------|---------|
| `workspace_id` | string (UUID) | owning workspace | `"ws-abc123"` |
| `user_id` | string (UUID) \| null | user who marked done; null if agent | `null` |
| `agent_id` | string (UUID) \| null | agent that completed the task | `"ag-001"` |
| `task_id` | string (UUID) | completed task id | `"task-001"` |
| `timestamp` | ISO 8601 | UTC | `"2026-06-15T09:20:00Z"` |
| `plan` | string enum | workspace plan | `"free"` |
| `task_age_seconds` | integer | seconds from task creation to completion | `600` |
| `reopen_count` | integer | how many times this task was reopened before this completion | `0` |
| `is_first_task_in_workspace` | boolean | true if this is the first ever completed task for the workspace | `true` |

#### Sample payload

```json
{
  "event": "dasflow.task.completed",
  "workspace_id": "ws-abc123-0000-0000-0000-000000000000",
  "user_id": null,
  "agent_id": "ag-001-0000-0000-0000-000000000000",
  "task_id": "task-001-0000-0000-0000-000000000000",
  "timestamp": "2026-06-15T09:20:00.000Z",
  "plan": "free",
  "task_age_seconds": 600,
  "reopen_count": 0,
  "is_first_task_in_workspace": true
}
```

#### Validation rules

- `task_age_seconds` must be ≥ 0.
- `is_first_task_in_workspace` must be computed server-side — do not trust client-provided values.

---

### Event: `dasflow.workspace.plan_upgraded`

| Field | Value |
|-------|-------|
| Event name | `dasflow.workspace.plan_upgraded` |
| Fires when | A workspace upgrades from one plan tier to a higher tier |
| Fired by | Server-side (post-payment confirmation) |
| Idempotency | Once per upgrade event; use `stripe_event_id` or equivalent as dedup key |
| Metrics fed | Free → paid conversion (L2 revenue), MRR |

#### Required properties

| Property | Type | Description | Example |
|----------|------|-------------|---------|
| `workspace_id` | string (UUID) | workspace | `"ws-abc123"` |
| `user_id` | string (UUID) | user who initiated upgrade | `"u-xyz789"` |
| `agent_id` | null | always null | `null` |
| `from_plan` | string enum | previous plan | `"free"` |
| `to_plan` | string enum | new plan | `"starter"` |
| `mrr_delta_usd` | float | incremental MRR from this upgrade | `29.00` |
| `days_since_signup` | integer | workspace age in days at upgrade time | `12` |
| `timestamp` | ISO 8601 | UTC | `"2026-06-27T14:00:00Z"` |

#### Validation rules

- `to_plan` must be a higher tier than `from_plan` (downgrades are a separate event, out of scope for MVP).
- `mrr_delta_usd` must be > 0.

---

### Event: `dasflow.budget_cap.hit`

| Field | Value |
|-------|-------|
| Event name | `dasflow.budget_cap.hit` |
| Fires when | A workspace's agent run is auto-paused because the monthly budget cap is reached |
| Fired by | Server-side |
| Idempotency | Once per calendar month per workspace; suppress duplicates within the same month |
| Metrics fed | L3 workspaces-hitting-cap; upsell signal feed |

#### Required properties

| Property | Type | Description | Example |
|----------|------|-------------|---------|
| `workspace_id` | string (UUID) | workspace | `"ws-abc123"` |
| `user_id` | null | always null — system event | `null` |
| `agent_id` | null | always null | `null` |
| `plan` | string enum | plan at cap-hit time | `"starter"` |
| `cap_amount_usd` | float | configured monthly cap | `50.00` |
| `spend_usd` | float | spend at cap-hit moment | `50.00` |
| `timestamp` | ISO 8601 | UTC | `"2026-07-22T11:30:00Z"` |

---

## 3. Funnel / Journey mapping

```
dasflow.workspace.created       ← step 1: acquisition
  ↓ (target: ≥ 60 % proceed)
dasflow.agent.created           ← step 2: activation starts
  ↓ (target: measure drop-off)
dasflow.task.created            ← step 3: first task
  ↓ (target: measure drop-off)
dasflow.heartbeat.run           ← step 4: agent executes
  ↓ (target: measure drop-off)
dasflow.task.completed          ← step 5: NORTH STAR
  ↓ (conditional, day 30+)
dasflow.workspace.plan_upgraded ← step 6: revenue
```

**Key funnel alert thresholds (to be tuned post-launch):**
- Step 1 → 2 (workspace → first agent): alert if < 50 % same-session
- Step 4 → 5 (heartbeat run → task done): alert if < 40 % completion rate
- Step 5 → 6 (first done → upgrade within 30 days): target ≥ 8 %

---

## 4. Dashboard / Query plan

| Metric | Query sketch |
|--------|-------------|
| North star (weekly) | `COUNT(task_id) / COUNT(DISTINCT workspace_id) WHERE event='dasflow.task.completed' AND date BETWEEN [week_start, week_end]` |
| Activation funnel | Step-ordered `COUNT(DISTINCT workspace_id)` per event, grouped by signup-week cohort |
| Week-4 WAU retention | `COUNT(DISTINCT workspace_id WHERE active week 4) / COUNT(DISTINCT workspace_id WHERE active week 1)` per cohort |
| LLM cost per task | `SUM(llm_cost_usd) / COUNT(task_id completed)` from heartbeat.run joined to task.completed, trailing 7 days |
| Budget-cap upsell list | `workspace_id WHERE dasflow.budget_cap.hit AND plan != 'growth'` — feed to CRM |

---

## 5. Implementation notes

| Item | Detail |
|------|--------|
| Delivery guarantee | At-least-once; consumers deduplicate on the IDs specified per event above |
| Backfill required? | No — events start at launch; no historical data to backfill |
| PII handling | `user_id` and `agent_id` are internal UUIDs — not email or name. No PII in any required field. `referrer_source` must not include raw query strings (strip before logging). |
| Staging validation | Fire synthetic events through the full funnel in staging; verify each event appears in the data warehouse within 60 seconds |
| Rollout | All workspaces from day one — no feature flag needed for server-side events |

---

## 6. Open questions for Engineering

1. What is the chosen event pipeline (Segment, Rudderstack, or custom)? Determines how `timestamp` and dedup keys are handled downstream.
2. Where is `llm_cost_usd` computed — the heartbeat runner or a post-run billing reconciliation job?
3. Should `dasflow.budget_cap.hit` suppress per-calendar-month or per-rolling-30-days?

---

## 7. Sign-off

| Role | Name | Date | Status |
|------|------|------|--------|
| Product Analyst | Product Analyst | 2026-05-18 | ✓ Draft complete |
| Engineering lead | | | ☐ Pending |
| Sr. PM | | | ☐ Pending |
