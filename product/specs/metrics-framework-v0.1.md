# DasFlow Metrics Framework

**Date:** 2026-05-18
**Author:** Product Analyst
**Status:** Draft — pending CPO review
**Covers:** DasFlow MVP launch through 60-day post-launch window

---

## North Star Metric

**Tasks completed per active workspace per week**

Why: a workspace that completes tasks regularly has proved that its agents deliver value. All upstream metrics (activation, retention, conversion) exist to grow this number.

Active workspace = any workspace that created ≥ 1 task and had ≥ 1 heartbeat in the trailing 7 days.

> MVP target: ≥ 3 tasks/active workspace/week by day 60

---

## Metric Hierarchy

### L1 — North Star

| Metric | Definition | Target (day 60) |
|--------|-----------|----------------|
| Tasks completed / active workspace / week | Count of tasks reaching `done` per workspace, 7-day rolling | ≥ 3 |

### L2 — Product Health (AARRR)

| Pillar | Metric | Definition | Target |
|--------|--------|-----------|--------|
| **Acquisition** | Signups (30-day cumulative) | Accounts created | 50 |
| **Acquisition** | Organic vs. paid channel split | % from each source | track only at MVP |
| **Activation** | Time to first completed task | Minutes from signup to first `done` task | ≤ 10 min |
| **Activation** | Day-0 agent creation rate | % of signups who create ≥ 1 agent within the session | ≥ 60 % |
| **Retention** | Week-4 WAU retention | Workspaces active in week 4 / workspaces active in week 1 | ≥ 20 % |
| **Retention** | Day-7 task-creator return rate | % of users who created a task in days 1–7 and return days 8–14 | ≥ 35 % |
| **Revenue** | Free → paid conversion (30-day) | % of free workspaces upgrading within 30 days | ≥ 8 % |
| **Revenue** | MRR | Recurring revenue from Starter + Growth + Enterprise | track |
| **Referral** | NPS (day-60 cohort survey) | Net Promoter Score | ≥ 30 |

### L3 — Feature-Level (operational)

| Feature | Metric | Notes |
|---------|--------|-------|
| Agent roster | Agents created per workspace | Health signal; workspaces with 0 agents churn fastest |
| Heartbeat runner | Heartbeats / agent / day | Measures utilization; low = idle agent, churn risk |
| Task inbox | Tasks created / workspace / week | Upstream driver of north star |
| Task inbox | Task completion rate | `done` / total tasks created; surfaces quality |
| Budget cap | Workspaces hitting cap | Proxy for heavy users; upsell signal |
| Onboarding | Onboarding funnel completion | Step-by-step drop-off (signup → agent → task → first done) |

---

## Measurement Approach

### Instrumentation layers

1. **Server-side events** — authoritative; fired by the API on state transitions (`task.done`, `agent.created`, `workspace.activated`, `heartbeat.run`).
2. **Client-side events** — supplementary; UI interactions (page views, button clicks, onboarding step completions).
3. **Aggregate rollups** — computed in the analytics warehouse (daily, weekly) from raw events.

### Instrumentation spec process

Every shipped feature must have an instrumentation spec in `specs/` before the engineering build begins. Use `specs/instrumentation-spec-template-v0.1.md` as the base.

### Tools (to be confirmed with CTO)

| Layer | Candidate | Decision by |
|-------|-----------|------------|
| Event pipeline | Segment / Rudderstack | 2026-06-01 |
| Analytics warehouse | BigQuery / Redshift | 2026-06-01 |
| Dashboards | Metabase / Grafana | 2026-06-01 |
| Session replay | PostHog / Heap | 2026-06-01 |
| Survey / NPS | Typeform / Delighted | 2026-06-01 |

---

## Reporting Cadence

| Report | Frequency | Owner | Audience |
|--------|-----------|-------|----------|
| Weekly metrics digest | Weekly, Monday | Product Analyst | CPO, Sr. PM |
| Monthly analytics review | Monthly, first Monday | Product Analyst | Full product team + CTO |
| Cohort retention snapshot | Monthly | Product Analyst | CPO |
| Funnel drop-off report | Monthly | Product Analyst | Sr. PM |
| NPS survey send + analysis | Day 60 post-signup | Product Analyst | CPO, CMO |

---

## Guardrail Metrics (must not degrade)

| Metric | Threshold |
|--------|----------|
| API p95 latency | ≤ 500 ms |
| Heartbeat success rate | ≥ 98 % |
| LLM cost per task | ≤ $0.10 (to protect margin) |
| Error rate (4xx/5xx) | ≤ 1 % of requests |

Guardrails are not targets — they are thresholds that trigger a freeze on non-critical work if breached.

---

## Open Questions

1. Which analytics warehouse does the CTO prefer? (determines instrumentation stack choices)
2. Should NPS be an in-app widget or email survey? (email requires a sending domain)
3. Will we instrument free-tier workspaces with the same granularity as paid? (cost vs. insight trade-off)
4. Privacy / GDPR posture — can we store workspace-level usage data without explicit consent prompt?
