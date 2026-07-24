---
id: DAS-1595
title: WS-G Deployment — ship the proof to the tenant VM (BLOCKED external)
status: blocked
assignee: sre-eng
author: ceo
dept: engineering
priority: p1
parent: DAS-1588
goal: mustaqil-ws-g-proof
spec: 007-mustaqil-ws-g-proof
implements: [FR-006]
stage: GATE-5
labels: [governance]
zone: docs/runbooks
depends_on: [DAS-1594]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 5 — Deployment (closes GATE-5 for WS-G).** Deliver the "shipped" bar for
the proof (Q7). SRE Lead accountable; Security Lead + Legal consulted.

- **FR-006/Q7:** "shipped" = merged to `main` + green CI + **deployed to the tenant VM**
  (one Linux VM, discovery Q2). Record the deploy runbook and the deploy evidence.
- The completed proof deploy is the final dimension of the 0→100 evidence trail —
  committed + hash-chained (DAS-1592).
- Record the deploy decision + evidence; a committed wave attestation (ADR-0031/0032).

**BLOCKED — external dependency.** There is **no provisioned tenant VM in this session**
(Q2 self-host infra is not stood up here). The deploy-to-VM step MUST NOT be skipped,
faked, or reported green (FR-006 / ADR-0020) — it is carried as `blocked` with this
precise reason until a tenant Linux VM is provisioned. Unblock condition: a reachable
in-tenant Linux VM + the Founder's go-ahead to deploy.

## Acceptance criteria
- [ ] Deploy runbook complete (`docs/runbooks/`): build, deploy-to-VM, health-check, rollback.
- [ ] Proof deployed to the tenant VM; deploy evidence recorded; final 0→100 evidence dimension committed + attested.
- [ ] "Shipped" bar met = merged + green CI + deployed to the VM (FR-006).
- [ ] Committed wave attestation; `diagnostics.py` 100/100; merged PR, green CI.

## Log
### 2026-07-24 — Senior Product Manager
Created by /daslab-plan (WS-G Deployment, GATE-5). status: **blocked** — external
dependency: no provisioned tenant VM in this session (Q2). Per FR-006 / ADR-0020 the
deploy-to-VM step is never faked or skipped; it waits as `blocked` with this reason
until a tenant Linux VM exists + the Founder approves the deploy. Not auto-dispatched
(external-dependency block).
</content>
