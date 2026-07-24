---
id: DAS-1569
title: WS-C Maintenance — scheduled health and eval of the loop and sandbox edge
status: todo
assignee: product-analyst
author: ceo
dept: engineering
priority: p2
parent: DAS-1561
goal: mustaqil-ws-c-loop
spec: 004-mustaqil-ws-c-loop
implements: [SC-005]
labels: [governance]
zone: docs/06-maintenance
depends_on: [DAS-1568]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 6 — Maintenance (closes GATE-6 for WS-C).** Schedule recurring health / eval
of the durable loop + per-task sandbox so drift is caught. COO accountable; Support Lead
consulted.

- A recurring **checkpoint-reconcile drift** check (graph state stays a faithful mirror of
  `board/tickets/`; no forked durable truth vs the ADR-0023 run-model / ADR-0031/0032
  ledger) and a **sandbox isolation probe** (a worker node still cannot reach the host /
  repo / another task / an unscoped credential).
- Wire it into the existing maintenance/eval cadence (the golden-eval / scheduled-run
  path), not a new daemon.
- Feed Founder-accepted learnings into the `daslab-learn` cadence (ADR-0029 G5) — a
  governed, Founder-reviewed compounding, not autonomous self-modification.

## Acceptance criteria
- [ ] A scheduled health/eval check exists for checkpoint-reconcile drift + sandbox isolation and runs on the maintenance cadence.
- [ ] A drift or isolation-probe failure surfaces as an alert / follow-up ticket (not silently).
- [ ] Learnings routed to `daslab-learn` (Founder-reviewed), not applied autonomously.
- [ ] Stage-board updated with GATE-6 closure. `board_lint`/validators green; merged PR, green CI.

## Log
### 2026-07-24 — CEO
Created by /daslab-plan (WS-C Maintenance, GATE-6). Checkpoint-reconcile drift + sandbox
isolation health checks on the eval cadence; learnings routed to daslab-learn.
</content>
