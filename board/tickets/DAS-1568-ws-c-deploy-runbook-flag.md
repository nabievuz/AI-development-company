---
id: DAS-1568
title: WS-C Deployment — runbook, loop flag stays OFF on merge, rollback via disabling the key
status: todo
assignee: sre-eng
author: ceo
dept: engineering
priority: p1
parent: DAS-1561
goal: mustaqil-ws-c-loop
spec: 004-mustaqil-ws-c-loop
implements: [FR-007]
stage: GATE-5
labels: [governance]
zone: docs/runbooks
depends_on: [DAS-1567]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 5 — Deployment (closes GATE-5 for WS-C).** Make the durable loop + sandbox
substrate shippable without changing dispatch. SRE Lead accountable; Security Lead
consulted.

- Write the runbook: how to enable `ws_c_langgraph_loop` for a supervised shadow window
  (Q4), how the loop reconciles with the ADR-0023 run-model, how to provision the sandbox
  host (points at DAS-1566), how to read checkpoints/attestation, and the
  **rollback = disable the `ws_c_langgraph_loop` key** (the substrate goes inert; the
  sandbox backend stays absent-by-default).
- **LG-5/FR-007:** the feature flag ships **OFF**; merging changes no dispatch behaviour;
  `/daslab-cycle` remains the fallback.
- Record the deploy decision + evidence; a committed wave attestation (ADR-0031/0032).

Do NOT flip the flag ON to autonomous drive — enabling shadow, then drive, is a later,
explicit Founder act after a clean shadow window, not this ticket.

## Acceptance criteria
- [ ] Runbook complete: enable-for-shadow, sandbox-host provisioning pointer (DAS-1566), checkpoint/attestation read, and rollback (disable the key) steps.
- [ ] Feature flag confirmed OFF at merge; a with-flag-off wave is byte-identical to pre-merge (evidence recorded).
- [ ] Rollback proven = disabling `ws_c_langgraph_loop` makes the substrate inert.
- [ ] Committed wave attestation; `diagnostics.py` 100/100; merged PR, green CI.

## Log
### 2026-07-24 — CEO
Created by /daslab-plan (WS-C Deployment, GATE-5). Flag OFF on merge (LG-5/FR-007);
rollback = disable the loop key. Enabling shadow/drive is a later explicit Founder act.
</content>
