---
id: DAS-1596
title: WS-G Maintenance — scheduled scorecard and evidence health checks
status: todo
assignee: product-analyst
author: ceo
dept: engineering
priority: p2
parent: DAS-1588
goal: mustaqil-ws-g-proof
spec: 007-mustaqil-ws-g-proof
implements: [SC-005]
labels: [governance]
zone: docs/06-maintenance
depends_on: [DAS-1595]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 6 — Maintenance (closes GATE-6 for WS-G).** Keep the proof machinery
honest over time so evidence-drift is caught. COO accountable; Support Lead consulted.

- A recurring check that the run-scorecard + evidence gate still score truthfully — the
  anti-gaming probe still fires, no completion-contract dimension silently degrades to a
  false-green, and the attestation chain stays intact.
- Wire it into the existing maintenance / golden-eval cadence (the scheduled-run path) —
  not a new daemon.
- Feed Founder-accepted learnings into the `daslab-learn` cadence (ADR-0029 G5) — a
  governed, Founder-reviewed compounding, not autonomous self-modification.

## Acceptance criteria
- [ ] A scheduled health check exists for scorecard/evidence-gate integrity (anti-gaming still fires, attestation chain intact) on the maintenance cadence.
- [ ] A drift or probe failure surfaces as an alert / follow-up ticket (not silently).
- [ ] Learnings routed to `daslab-learn` (Founder-reviewed), not applied autonomously.
- [ ] Stage-board updated with GATE-6 closure. `diagnostics.py` 100/100; `board_lint`/validators green (SC-005); merged PR, green CI.

## Log
### 2026-07-24 — Senior Product Manager
Created by /daslab-plan (WS-G Maintenance, GATE-6). Scheduled scorecard/evidence-gate
health on the eval cadence; SC-005 validators; learnings to daslab-learn (Founder-reviewed).
</content>
