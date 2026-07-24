---
id: DAS-1618
title: WS-F Development — close real gaps in the shadow and evidence tooling
status: todo
assignee: sre-eng
author: ceo
dept: engineering
priority: p1
parent: DAS-1615
goal: mustaqil-ws-f-tempo
spec: 010-mustaqil-ws-f-tempo
implements: [FR-002, FR-005]
labels: [governance, security]
zone: scripts
depends_on: [DAS-1617]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 3 — Development (closes GATE-3 for WS-F, part 1).** Fix only the
**real gaps** DAS-1617's evidence map surfaced — never rebuild `loop_controller.py`,
`break_glass.py`, or `check_heartbeat_readiness.py` from scratch.

- As of this ticket's creation, `check_heartbeat_readiness.py` reports **0/3
  consecutive clean days from 0 history rows** — the shadow window has not begun
  accumulating because waves are not yet landing as *counted* (merged PR + green CI
  + T7, per the anti-gaming regime) and/or `board/.metrics-history.jsonl` is not
  being fed daily. If DAS-1617 confirms this is the blocking gap, this ticket closes
  it: wire (or confirm wired) the counted-wave → metrics-history feed path
  (`scripts/metrics_history_feeder.py` or equivalent) so real shadow days can start
  accumulating once dispatch resumes.
- Fix any other SI-1…SI-7 evidence gap DAS-1617 flagged (e.g. a missing test, a
  stale reporter path) — each fix traces to one flagged gap, no speculative rework.
- Do **not** touch `config/loop.yaml`'s mode/`auto_apply`, do **not** flip
  `heartbeat_enabled`, do **not** widen SI-5/SI-6 caps.

## Acceptance criteria
- [ ] Every gap DAS-1617 flagged in the evidence map is closed with a named fix,
      or explicitly re-classified (with reason) as out of WS-F's scope.
- [ ] The counted-wave → shadow-metrics feed path confirmed working (or fixed) so
      `check_heartbeat_readiness.py` can accumulate real clean-day rows once waves
      resume — verified by a dry-run / test, not asserted.
- [ ] No governance-or-policy file (`loop.yaml`, `features.yaml`'s `heartbeat_enabled`
      value) edited by this ticket.
- [ ] `diagnostics.py` 100/100; merged PR, green CI where applicable.

## Log
### 2026-07-24 — Senior Product Manager
Created by /daslab-plan (WS-F Development, part 1). Scoped to closing only the real
gaps DAS-1617's evidence map surfaces (the current 0/3-clean-day/0-history-row state
is the likely candidate) — no rebuild of existing WS4 machinery.
