---
id: DAS-1550
title: WS-A Deployment — runbook, flag stays OFF on merge, rollback via mcp.json removal
status: todo
assignee: sre-eng
author: ceo
dept: engineering
priority: p1
parent: DAS-1544
goal: mustaqil-ws-a-reach
spec: 002-mustaqil-ws-a-reach
implements: [FR-004]
stage: GATE-5
labels: [security]
zone: docs/runbooks
depends_on: [DAS-1549]
created: 2026-07-23
updated: 2026-07-23
---

## Description

**AADL Stage 5 — Deployment (closes GATE-5 for WS-A).** Make the bridge shippable
without changing dispatch. SRE Lead accountable; Security Lead + Legal consulted.

- Finalize the runbook — fold in `docs/runbooks/ws-a-tool-bridge.md`: how to enable the
  flag for a specific role, how to add a domain to the egress allow-list, how to read
  audit events, and the **rollback = delete the `.mcp.json` entry**.
- **TB-5:** the feature flag ships **OFF**; merging changes no dispatch behaviour.
- Record the deploy decision + evidence; a committed wave attestation (ADR-0031/0032).

Do NOT flip the flag ON — enabling is a later, explicit Founder act, not this ticket.

## Acceptance criteria
- [ ] Runbook complete and folded in (`docs/runbooks/ws-a-tool-bridge.md`): enable-per-role, egress allow-list edit, audit-read, and rollback steps.
- [ ] Feature flag confirmed OFF at merge; a with-flag-off wave is byte-identical to pre-merge (evidence recorded).
- [ ] Rollback proven = removing the `.mcp.json` entry fully removes the tool.
- [ ] Committed wave attestation; `diagnostics.py` 100/100; merged PR, green CI.

## Log
### 2026-07-23 — CEO
Created by /daslab-plan (WS-A Deployment, GATE-5). Flag OFF on merge (TB-5); rollback via .mcp.json removal.
