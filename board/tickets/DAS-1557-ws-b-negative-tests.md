---
id: DAS-1557
title: WS-B Testing — dispatch equivalence, missing model rejection, budget and credit pause
status: todo
assignee: qa-eng
author: ceo
dept: engineering
priority: p1
parent: DAS-1552
goal: mustaqil-ws-b-runner
spec: 003-mustaqil-ws-b-runner
implements: [SC-001, SC-002, SC-003, SC-004]
labels: [security]
zone: tests
depends_on: [DAS-1555, DAS-1556]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 4 — Testing (closes GATE-4 for WS-B).** Prove the runner holds
its governance invariants with positive and adversarial tests.

Cover:
- **SC-001:** a headless dispatch of a ticket (and, via the wave call, a
  full wave) produces the same board state, event stream, and attestation an
  equivalent interactive `/daslab-cycle` dispatch would produce.
- **SC-002:** a dispatch without an explicit `model` argument is rejected
  before it reaches the model call.
- **SC-003:** with the feature flag OFF, the runner is inert / import-only,
  and an interactive wave's dispatch behaviour is byte-identical to
  pre-merge; flipping the flag ON changes no interactive-wave behaviour.
- **SC-004:** a budget-breach scenario (per-run or per-day cap) and a
  monthly-credit-exhaustion scenario each evaluate to idle + alert /
  sanctioned pause — never a false-green or an unhandled crash.

## Acceptance criteria
- [ ] Dispatch-equivalence test exists and PASSES for SC-001 (headless vs. interactive wave produce the same board/event/attestation outcome).
- [ ] Missing-model rejection test exists and PASSES for SC-002.
- [ ] Flag-off no-op test exists and PASSES for SC-003 (byte-identical interactive dispatch with the flag OFF).
- [ ] Budget-breach and credit-exhaustion negative tests exist and PASS for SC-004 (idle+alert / sanctioned pause, not a crash or false-green).
- [ ] Overall pytest green in CI. Merged PR, green CI.

## Log
### 2026-07-24 — Senior PM
Created by `/daslab-plan` (WS-B Testing). SC-001..SC-004 dispatch-equivalence,
missing-model, flag-off, and budget/credit-pause negative tests.
