---
id: DAS-1556
title: WS-B Development — admission gateway, Claude subscription auth, budget and credit ceiling
status: todo
assignee: backend-eng-1
author: ceo
dept: engineering
priority: p1
parent: DAS-1552
goal: mustaqil-ws-b-runner
spec: 003-mustaqil-ws-b-runner
implements: [FR-002, FR-006, FR-007, FR-008]
labels: [security]
zone: scripts
depends_on: [DAS-1554]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 3 — Development (closes GATE-3 for WS-B, part 2).** Build the
admission-gateway, auth, and budget-ceiling integration per the DAS-1554
design.

- **SR-2 — explicit model, real admission gateway:** every dispatch passes
  `model` explicitly, sourced from `governance/policies/model-allocation.md`
  (frontmatter alone stays untrusted, per LAW 3). This becomes the real
  ADR-0009 admission gateway: it governs which model dispatches, under which
  per-dispatch budget, honoring the ADR-0027 SI-5 ceiling rather than
  reopening it.
- **Claude-account auth (Q9):** authenticate via a Claude-subscription account
  (Pro/Max/Team/Enterprise) using account/OAuth authentication, never a
  metered API key; keep the auth path behind the admission layer so it stays
  swappable.
- **Budget + monthly-credit ceiling:** wire the `mustaqil:` per-run/per-day
  caps (`config/budgets.yaml`, DAS-1543) together with the monthly
  subscription-credit outer ceiling; a wave that would breach either
  evaluates to **idle + alert** (`on_breach: idle_and_alert`), never
  proceeding or reporting a false success. Keep metered usage-credit overflow
  **disabled** by default.
- **Sanctioned pause:** credit exhaustion is handled as a pause that resumes
  on refresh — surfaced as a sanctioned halt (comparable to a gate halt), not
  a crash, a silent stop, or a failed run.

Distinct repo zone from DAS-1555 so the two Development tickets can proceed
without a same-zone wave collision.

## Acceptance criteria
- [ ] Every dispatch through the runner carries an explicit `model` argument sourced from `model-allocation.md`; a dispatch without one is rejected before it reaches the model call.
- [ ] Authentication path uses a Claude-subscription account (account/OAuth), not a metered API key; the auth path sits behind the admission layer.
- [ ] Budget-breach (`mustaqil:` per-run/per-day caps) and monthly-credit-exhaustion both evaluate to idle + alert / sanctioned pause, proven by at least one test each; metered overflow stays disabled by default.
- [ ] Feature-flagged OFF by default (shared `ws_b_agent_sdk_runner` key with DAS-1555); flag-off behaviour unchanged. `diagnostics.py` 100/100. Merged PR, green CI.

## Log
### 2026-07-24 — Senior PM
Created by `/daslab-plan` (WS-B Development, part 2). SR-2 explicit-model/admission
gateway + Claude-account auth + budget/credit-ceiling integration; distinct zone
(`scripts`) from DAS-1555 (`daslab_sdk`) for parallel wave dispatch.
