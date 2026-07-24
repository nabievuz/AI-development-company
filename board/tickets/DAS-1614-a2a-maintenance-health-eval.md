---
id: DAS-1614
title: A2A Maintenance — scheduled health and eval of the outbound endpoint
status: backlog
assignee: product-analyst
author: ceo
dept: engineering
priority: p2
parent: DAS-1606
goal: mustaqil-a2a-outbound
spec: 009-mustaqil-a2a-outbound
implements: [SC-003, SC-005]
labels: [security]
zone: docs/06-maintenance
depends_on: [DAS-1613]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 6 — Maintenance (closes GATE-6 for A2A OUTBOUND).**

Stand up the ongoing health/eval cadence for the A2A surface once it is live:

- Scheduled check that the in-tenant boundary still holds (no config drift
  toward a hosted relay/registry) — feeds SC-003.
- Scheduled check that the flag/publish state matches what the Founder last
  authorized (no silent drift from OFF to ON, or from internal-only to
  published, without a corresponding logged Founder act).
- Periodic re-run of the negative-test suite (DAS-1612) against the live
  surface, folded into the existing golden-eval / diagnostics cadence — feeds
  SC-005's "stays green" property over time, not just at merge.
- Report cadence: fold findings into the existing product analytics review
  (per `product/CLAUDE.md` Success Metrics — monthly product analytics review).

## Acceptance criteria
- [ ] A scheduled check verifies the in-tenant boundary holds over time (SC-003).
- [ ] A scheduled check verifies flag/publish state matches the last logged Founder act (no drift).
- [ ] The negative-test suite (DAS-1612) is folded into a recurring eval cadence.
- [ ] Findings are reported through the existing monthly product analytics review.
- [ ] `diagnostics.py` 100/100; `board_lint`/validators green; no `project:` field (R9).

## Log
### 2026-07-24 — Senior Product Manager
Created by `/daslab-plan` (A2A Maintenance). Depends on DAS-1613 (Deployment).
Gated behind DAS-1606's binding sequencing note (after WS-B, deferred until
after WS-G's proof per Q12) — left in `status: backlog` until that gate opens.
This closes the AADL 6-gate template for the A2A OUTBOUND epic (DAS-1606).
