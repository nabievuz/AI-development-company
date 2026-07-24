---
id: DAS-1587
title: WS-E Maintenance — scheduled health and eval of the tenant hardening surface
status: todo
assignee: product-analyst
author: ceo
dept: engineering
priority: p2
parent: DAS-1579
goal: mustaqil-ws-e-tenant
spec: 006-mustaqil-ws-e-tenant
implements: [SC-005]
labels: [security]
zone: docs/06-maintenance
depends_on: [DAS-1586]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 6 — Maintenance (closes GATE-6 for WS-E).** Schedule recurring health / eval
of the tenant hardening surface so drift is caught. COO accountable; Support Lead
consulted.

- A recurring check for **RBAC drift** (a principal or role gaining gate-approval /
  run-trigger authority outside the documented Founder-only model), an **audit-export
  redaction probe** (exported events still redacted, still read-only, no board write-back),
  a **guardrail probe** (Presidio+classifier+policy still detects planted PII/secrets), and
  an **in-tenant precondition check** (no model/observability/tool endpoint drifted to a
  hosted target — TN-1 holds).
- Wire it into the existing maintenance/eval cadence (the golden-eval / scheduled-run
  path), not a new daemon.
- Feed Founder-accepted learnings into the `daslab-learn` cadence (ADR-0029 G5) — a
  governed, Founder-reviewed compounding, not autonomous self-modification.

## Acceptance criteria
- [ ] A scheduled health/eval check exists for RBAC drift + audit-export redaction + guardrail probe + TN-1 in-tenant precondition, running on the maintenance cadence.
- [ ] A drift or probe failure surfaces as an alert / follow-up ticket (not silently).
- [ ] Learnings routed to `daslab-learn` (Founder-reviewed), not applied autonomously.
- [ ] Stage-board updated with GATE-6 closure. `board_lint`/validators green; merged PR, green CI.

## Log
### 2026-07-24 — CEO
Created by /daslab-plan (WS-E Maintenance, GATE-6). RBAC drift + audit-export redaction + guardrail probe + TN-1 in-tenant precondition health checks on the eval cadence. Depends on the BLOCKED Deployment DAS-1586 — waits behind it until the tenant VM is live.
