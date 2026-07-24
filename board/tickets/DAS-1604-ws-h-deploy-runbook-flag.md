---
id: DAS-1604
title: WS-H Deployment — runbook, flag stays OFF on merge, systemd or launchd opt-in, degrade-to-static default
status: backlog
assignee: sre-eng
author: ceo
dept: engineering
priority: p1
parent: DAS-1597
goal: mustaqil-ws-h-control
spec: 008-mustaqil-ws-h-control
implements: [FR-006]
stage: GATE-5
labels: [security]
zone: docs/runbooks
depends_on: [DAS-1603]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 5 — Deployment (closes GATE-5 for WS-H).** Make the control plane shippable
without changing dispatch. SRE Lead accountable; Security Lead + Legal consulted.

- Finalize the runbook — fold in `docs/runbooks/ws-h-control-plane.md`: how to install
  (online + the vendored-wheels offline path), how to configure the RBAC token map in the
  tenant vault, how the Founder opts the process in (systemd on Ubuntu / launchd on
  macOS), how to read the audit trail, and the **degrade-to-static** default when the
  process is off.
- **FR-006 / CP-5:** the feature flag ships **OFF** and the process is not enabled by
  default; merging changes no dispatch behaviour — the static read cockpit (ADR-0028) is
  the shipped default (SC-004). The server dispatches nothing on its own.
- Record the deploy decision + evidence; a committed wave attestation (ADR-0031/0032).

Do NOT flip the flag ON or enable the process — enabling is a later, explicit Founder
act (deploy to the tenant VM with Founder-only RBAC, Q6/Q7), not this ticket. This
GATE-5 slice doubles as the WS-G PROOF "shipped" evidence (ADR-0037): merged + green CI
+ deployed to the tenant VM is demonstrated on this dashboard slice.

## Acceptance criteria
- [ ] Runbook complete and folded in (`docs/runbooks/ws-h-control-plane.md`): online + offline-vendored install, RBAC-vault setup, systemd/launchd opt-in, audit-read, and the degrade-to-static default.
- [ ] Feature flag confirmed OFF at merge and the process not default-enabled; a flag-off / process-absent surface is byte-identical to pre-merge — the static cockpit is the shipped default (evidence recorded, SC-004).
- [ ] Committed wave attestation; `diagnostics.py` 100/100; merged PR, green CI.
- [ ] Deploy decision recorded; the WS-G PROOF "shipped to tenant VM" cross-reference noted for the Founder-gated enablement.

## Log
### 2026-07-24 — CEO
Created by /daslab-plan (WS-H Deployment, GATE-5). Flag OFF on merge, process opt-in only
(FR-006); degrade-to-static default; runbook folded in. Doubles as the WS-G PROOF shipped
evidence. Enabling the process is a later explicit Founder act — not this ticket.
