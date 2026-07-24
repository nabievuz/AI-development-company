---
id: DAS-1605
title: WS-H Maintenance — scheduled health and eval of the control edge
status: backlog
assignee: product-analyst
author: ceo
dept: engineering
priority: p2
parent: DAS-1597
goal: mustaqil-ws-h-control
spec: 008-mustaqil-ws-h-control
implements: [SC-005]
labels: [security]
zone: docs/06-maintenance
depends_on: [DAS-1604]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 6 — Maintenance (closes GATE-6 for WS-H).** Schedule recurring health / eval
of the governed control plane so drift is caught. COO accountable; Support Lead consulted.

- A recurring check for **RBAC drift** (a role or token granted outside the documented
  Founder-only-approval posture — e.g. a non-Founder that can reach an approve endpoint)
  and an **audit-redaction probe** (governed-write audit records still land and stay
  redacted per ADR-0012).
- A recurring check that the flag stays OFF / the process stays opt-in and the
  degrade-to-static base case still holds (no accidental daemon).
- Wire it into the existing maintenance/eval cadence (the golden-eval / scheduled-run
  path), not a new daemon.
- Feed Founder-accepted learnings into the `daslab-learn` cadence (ADR-0029 G5) — a
  governed, Founder-reviewed compounding, not autonomous self-modification.

## Acceptance criteria
- [ ] A scheduled health/eval check exists for RBAC drift + audit-redaction + flag-OFF/degrade-to-static and runs on the maintenance cadence.
- [ ] A drift or redaction-probe failure surfaces as an alert / follow-up ticket (not silently).
- [ ] Learnings routed to `daslab-learn` (Founder-reviewed), not applied autonomously.
- [ ] Stage-board updated with GATE-6 closure. `board_lint`/validators green; merged PR, green CI.

## Log
### 2026-07-24 — CEO
Created by /daslab-plan (WS-H Maintenance, GATE-6). RBAC-drift + audit-redaction +
flag-OFF/degrade-to-static health checks on the eval cadence; learnings to daslab-learn.
