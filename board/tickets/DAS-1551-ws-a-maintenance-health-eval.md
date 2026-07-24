---
id: DAS-1551
title: WS-A Maintenance — scheduled health and eval of the tool edge
status: todo
assignee: product-analyst
author: ceo
dept: engineering
priority: p2
parent: DAS-1544
goal: mustaqil-ws-a-reach
spec: 002-mustaqil-ws-a-reach
implements: [SC-004]
labels: [security]
zone: docs/06-maintenance
depends_on: [DAS-1550]
created: 2026-07-23
updated: 2026-07-23
---

## Description

**AADL Stage 6 — Maintenance (closes GATE-6 for WS-A).** Schedule recurring health /
eval of the governed tool edge so drift is caught. COO accountable; Support Lead
consulted.

- A recurring check for **allow-list drift** (a role or tool granted outside the
  documented allow-list) and a **redaction probe** (tool events still redacted).
- Wire it into the existing maintenance/eval cadence (the golden-eval / scheduled-run
  path), not a new daemon.
- Feed Founder-accepted learnings into the `daslab-learn` cadence (ADR-0029 G5) — a
  governed, Founder-reviewed compounding, not autonomous self-modification.

## Acceptance criteria
- [ ] A scheduled health/eval check exists for allow-list drift + redaction and runs on the maintenance cadence.
- [ ] A drift or redaction-probe failure surfaces as an alert / follow-up ticket (not silently).
- [ ] Learnings routed to `daslab-learn` (Founder-reviewed), not applied autonomously.
- [ ] Stage-board updated with GATE-6 closure. `board_lint`/validators green; merged PR, green CI.

## Log
### 2026-07-23 — CEO
Created by /daslab-plan (WS-A Maintenance, GATE-6). Allow-list drift + redaction health checks on the eval cadence.
