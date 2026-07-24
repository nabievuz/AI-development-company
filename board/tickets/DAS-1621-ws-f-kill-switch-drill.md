---
id: DAS-1621
title: WS-F Testing — kill-switch and break-glass drill, zero gate violations
status: todo
assignee: qa-eng
author: ceo
dept: engineering
priority: p1
parent: DAS-1615
goal: mustaqil-ws-f-tempo
spec: 010-mustaqil-ws-f-tempo
implements: [SC-002]
labels: [governance, security]
zone: tests
depends_on: [DAS-1620]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 4 — Testing (closes GATE-4 for WS-F, part 2).** Run the dedicated
kill-switch / break-glass safety-rail drill, reusing DAS-1478's existing drill
machinery rather than authoring a new one, and confirm SI-3 and SI-6 hold under
WS-F's closure.

- **SI-3 (break-glass honored):** activate `scripts/break_glass.py`, confirm a
  `--tick` consults `is_active(now)` and dispatches nothing while active; confirm
  auto-expiry at 60 minutes; confirm the heartbeat never activates/clears
  break-glass itself.
- **SI-6 (max-concurrent-waves = 1):** confirm a `--tick` firing while a prior
  heartbeat-dispatched wave is in flight evaluates to idle (no overlapping wave).
- **Event-log check:** scan `board/.events.jsonl` / interrupt-card records for the
  drill window and confirm **zero gate/approval violations** — no auto-approved
  gate, no auto-answered interrupt-card, no `heartbeat_enabled` write.

## Acceptance criteria
- [ ] Break-glass drill run: dispatch correctly halts while active, resumes only
      after expiry/deactivation, auto-expiry confirmed at 60 minutes.
- [ ] Max-concurrent-waves = 1 confirmed: an overlapping `--tick` evaluates to idle.
- [ ] Event log scanned for the drill window: **zero** gate/approval violations
      recorded — this is SC-002's pass condition, stated plainly in the log.
- [ ] `diagnostics.py` 100/100; reuses (does not fork) DAS-1478's drill tests; merged
      PR if any code changed, else a recorded local-run transcript.

## Log
### 2026-07-24 — Senior Product Manager
Created by /daslab-plan (WS-F Testing, part 2). Dedicated kill-switch/break-glass
drill (SI-3/SI-6) reusing DAS-1478's existing machinery; confirms zero gate/approval
violations in the event log per SPEC-010 SC-002.
