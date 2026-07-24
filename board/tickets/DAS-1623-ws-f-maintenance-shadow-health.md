---
id: DAS-1623
title: WS-F Maintenance — recurring shadow-window and credit-ceiling health check
status: todo
assignee: product-analyst
author: ceo
dept: engineering
priority: p2
parent: DAS-1615
goal: mustaqil-ws-f-tempo
spec: 010-mustaqil-ws-f-tempo
implements: [SC-001, SC-003]
labels: [governance, security]
zone: docs/06-maintenance
depends_on: [DAS-1622]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 6 — Maintenance (closes GATE-6 for WS-F).** Schedule a recurring
health check of the tempo substrate's evidence trail so drift is caught whether the
Founder has flipped the flag yet or not. COO accountable; SRE Lead consulted.

- A recurring **shadow-window check**: re-run `check_heartbeat_readiness.py` (or
  the DAS-1619 go/no-go report) on the existing maintenance/eval cadence and record
  the clean-day count trend — before go-live this tracks progress toward the ≥3-day
  bar; after go-live it becomes a live-health check (no silent regression back
  below the bar).
- A recurring **credit-ceiling check**: confirm the monthly Claude-subscription
  credit ceiling in `config/budgets.yaml` still matches the live plan terms
  (per the MUSTAQIL BUDGET precondition's "verify at build time" note) and that
  spend stays inside it.
- Feed Founder-accepted learnings into the `daslab-learn` cadence (ADR-0029 G5) —
  governed, Founder-reviewed compounding, never autonomous self-modification.
- Wire into the existing maintenance/eval cadence, not a new daemon (consistent with
  ADR-0027 SI-1 "not a daemon").

## Acceptance criteria
- [ ] A scheduled health check exists for the shadow-window clean-day trend and the
      credit-ceiling match, running on the existing maintenance cadence.
- [ ] A regression (clean-day count dropping post-go-live, or a credit-ceiling
      mismatch) surfaces as an alert / follow-up ticket — never silently.
- [ ] Learnings routed to `daslab-learn` (Founder-reviewed), not applied
      autonomously.
- [ ] Stage-board updated with GATE-6 closure. `board_lint`/validators green; merged
      PR if code changed, else a recorded local-run transcript.

## Log
### 2026-07-24 — Senior Product Manager
Created by /daslab-plan (WS-F Maintenance, GATE-6). Recurring shadow-window trend +
credit-ceiling health checks on the existing eval cadence; feeds daslab-learn.
