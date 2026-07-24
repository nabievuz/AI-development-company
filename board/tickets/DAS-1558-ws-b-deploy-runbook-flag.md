---
id: DAS-1558
title: WS-B Deployment — runbook, flag stays OFF on merge, rollback plan
status: todo
assignee: sre-eng
author: ceo
dept: engineering
priority: p1
parent: DAS-1552
goal: mustaqil-ws-b-runner
spec: 003-mustaqil-ws-b-runner
implements: [FR-005]
stage: GATE-5
labels: [security]
zone: docs/runbooks
depends_on: [DAS-1557]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 5 — Deployment (closes GATE-5 for WS-B).** Make the headless
runner shippable without changing dispatch behaviour. SRE Lead accountable;
Security Lead + Legal consulted.

- Write the runbook (`docs/runbooks/ws-b-agent-sdk-runner.md`): how to invoke
  the runner for a single ticket and for `run_wave`, how the explicit-model
  and budget/credit-ceiling wiring is verified before a real dispatch, how to
  read the emitted attestation, and the **rollback = flip
  `ws_b_agent_sdk_runner` back to `false`** (no code removal required, per
  ADR-0019).
- **Re-verify the Planning-stage standing item** before recommending any
  future flip: confirm the *live* Claude plan's Agent-SDK terms, per-plan
  credit, and headless-use policy (the marker carried from DAS-1553 — the
  2026-06-15 credit model was announced then paused). Record the verification
  outcome in this ticket's log; if still unresolved, keep the flag OFF and
  say so explicitly — do not flip on an unverified assumption.
- **FR-005/SR-5:** the feature flag ships **OFF**; merging changes no
  dispatch behaviour.
- Record the deploy decision + evidence; a committed wave attestation
  (ADR-0031/0032).

Do NOT flip the flag ON — enabling is a later, explicit Founder act, not this
ticket.

## Acceptance criteria
- [ ] Runbook complete (`docs/runbooks/ws-b-agent-sdk-runner.md`): invoke-single-ticket, invoke-wave, verify-before-dispatch, read-attestation, and rollback (flag flip) steps.
- [ ] The Q9 build-time verification item is re-checked here (live plan terms / per-plan credit / headless-use policy) and the outcome recorded; the flag stays OFF regardless of outcome unless the Founder separately authorizes a flip.
- [ ] Feature flag confirmed OFF at merge; a with-flag-off wave is byte-identical to pre-merge (evidence recorded).
- [ ] Committed wave attestation; `diagnostics.py` 100/100; merged PR, green CI.

## Log
### 2026-07-24 — Senior PM
Created by `/daslab-plan` (WS-B Deployment, GATE-5). Flag OFF on merge (SR-5);
rollback via flag flip; carries forward the Planning-stage Q9 re-verification item.
