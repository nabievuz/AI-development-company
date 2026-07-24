---
id: DAS-1559
title: WS-B Maintenance — scheduled health and eval of the runner path
status: todo
assignee: product-analyst
author: ceo
dept: engineering
priority: p2
parent: DAS-1552
goal: mustaqil-ws-b-runner
spec: 003-mustaqil-ws-b-runner
implements: [SC-005]
labels: [security]
zone: docs/06-maintenance
depends_on: [DAS-1558]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 6 — Maintenance (closes GATE-6 for WS-B).** Schedule recurring
health/eval of the headless runner path so drift is caught. COO accountable;
Support Lead consulted.

- A recurring check for **dispatch-equivalence drift** (a headless dispatch
  starts producing a board/event/attestation outcome that diverges from an
  equivalent interactive dispatch) and for **budget-ceiling drift** (the
  `mustaqil:` caps or the monthly-credit ceiling wiring silently stops
  enforcing idle+alert / sanctioned pause).
- Wire it into the existing maintenance/eval cadence (the golden-eval /
  scheduled-run path), not a new daemon.
- Feed Founder-accepted learnings into the `daslab-learn` cadence
  (ADR-0029 G5) — a governed, Founder-reviewed compounding, not autonomous
  self-modification.

## Acceptance criteria
- [ ] A scheduled health/eval check exists for dispatch-equivalence drift and budget/credit-ceiling drift, and runs on the maintenance cadence.
- [ ] A drift or budget-ceiling failure surfaces as an alert / follow-up ticket (not silently).
- [ ] Learnings routed to `daslab-learn` (Founder-reviewed), not applied autonomously.
- [ ] Stage-board updated with GATE-6 closure. `board_lint`/validators green; merged PR, green CI.

## Log
### 2026-07-24 — Senior PM
Created by `/daslab-plan` (WS-B Maintenance, GATE-6). Dispatch-equivalence and
budget/credit-ceiling drift health checks on the eval cadence.
