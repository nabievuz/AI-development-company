---
id: DAS-1577
title: WS-D Maintenance — scheduled health and eval of the Langfuse lens and tool-admission edge
status: todo
assignee: product-analyst
author: ceo
dept: engineering
priority: p2
parent: DAS-1570
goal: mustaqil-ws-d-lens
spec: 005-mustaqil-ws-d-lens
implements: [SC-005]
labels: [security]
zone: docs/06-maintenance
depends_on: [DAS-1576]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 6 — Maintenance (closes GATE-6 for WS-D).** Schedule recurring
health/eval of the observability lens and the tool-admission edge so drift is
caught. COO accountable; Support Lead consulted.

- A recurring check for **redaction drift** on the exporter (the redaction
  probe still passes on each new span shape) and for **in-tenant target
  drift** (the exporter config still resolves to a self-host endpoint, never a
  hosted one).
- A recurring check for **tool-admission allow-list drift** on
  promptfoo/AgentShield/Presidio (a role or tool granted outside the
  documented allow-list), reusing the same drift check WS-A's DAS-1551
  established rather than duplicating it.
- Wire it into the existing maintenance/eval cadence (the golden-eval /
  scheduled-run path), not a new daemon.
- Feed Founder-accepted learnings into the `daslab-learn` cadence
  (ADR-0029 G5) — a governed, Founder-reviewed compounding, not autonomous
  self-modification.

## Acceptance criteria
- [ ] A scheduled health/eval check exists for exporter redaction + in-tenant-target drift and runs on the maintenance cadence.
- [ ] A scheduled health/eval check exists for promptfoo/AgentShield/Presidio allow-list drift, reusing (not duplicating) the WS-A drift mechanism.
- [ ] A drift or redaction-probe failure surfaces as an alert / follow-up ticket (not silently).
- [ ] Learnings routed to `daslab-learn` (Founder-reviewed), not applied autonomously.
- [ ] Stage-board updated with GATE-6 closure. `board_lint`/validators green; merged PR, green CI.

## Log
### 2026-07-24 — Senior Product Manager
Created by /daslab-plan (WS-D Maintenance, GATE-6). Exporter redaction +
in-tenant-target drift checks; reuse of WS-A's tool-admission drift mechanism
for the eval/guardrail shortlist.
