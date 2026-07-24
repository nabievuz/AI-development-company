---
id: DAS-1576
title: WS-D Deployment — self-host Langfuse runbook, flag stays OFF on merge
status: todo
assignee: sre-eng
author: ceo
dept: engineering
priority: p1
parent: DAS-1570
goal: mustaqil-ws-d-lens
spec: 005-mustaqil-ws-d-lens
implements: [FR-004, FR-006]
stage: GATE-5
labels: [security]
zone: docs/runbooks
depends_on: [DAS-1575]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 5 — Deployment (closes GATE-5 for WS-D).** Make the exporter and
tool admission shippable without changing dispatch. SRE Lead accountable;
Security Lead + Legal consulted.

- Write the runbook: how to stand up **self-host Langfuse** on the tenant VM
  (ADR-0038 TN-1), how to point the exporter's config at it, how to enable the
  flag for a specific role/tool, how to add a promptfoo/AgentShield/Presidio
  overlay allow-list entry, how to read audit events, and **rollback** = disable
  the flag / remove the exporter and sidecar entries.
- **FR-004:** the feature flag ships **OFF**; merging changes no dispatch
  behaviour.
- Note explicitly (FR-006) that publishing the Langfuse endpoint beyond the
  tenant, or pointing the exporter at a hosted project, is a later, explicit
  **Founder** act — NOT this ticket.
- Record the deploy decision + evidence; a committed wave attestation
  (ADR-0031/0032).

Do NOT flip the flag ON — enabling is a later, explicit Founder act, not this
ticket.

## Acceptance criteria
- [ ] Runbook complete: self-host Langfuse setup, exporter config, per-role/tool enable steps, egress/allow-list edit, audit-read, and rollback steps.
- [ ] Feature flag confirmed OFF at merge; a with-flag-off wave is byte-identical to pre-merge (evidence recorded).
- [ ] Rollback proven = disabling the flag / removing the exporter and sidecar entries fully removes the lens and the three tools.
- [ ] Committed wave attestation; `diagnostics.py` 100/100; merged PR, green CI.

## Log
### 2026-07-24 — Senior Product Manager
Created by /daslab-plan (WS-D Deployment, GATE-5). Self-host Langfuse note;
flag OFF on merge (FR-004); publishing = a later Founder act (FR-006), not
this ticket.
