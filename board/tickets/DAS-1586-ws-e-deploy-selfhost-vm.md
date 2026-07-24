---
id: DAS-1586
title: WS-E Deployment — self-host the tenant hardening stack on a real Linux VM
status: blocked
assignee: sre-eng
author: ceo
dept: engineering
priority: p1
parent: DAS-1579
goal: mustaqil-ws-e-tenant
spec: 006-mustaqil-ws-e-tenant
implements: [FR-008]
stage: GATE-5
labels: [security]
zone: docs/runbooks
depends_on: [DAS-1585]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 5 — Deployment (closes GATE-5 for WS-E).** Stand up the WS-E tenant
hardening stack on a REAL in-tenant Linux VM and prove it in place. SRE Lead accountable;
Security Lead + COO consulted.

- Provision the Ubuntu (Linux-first) tenant VM; deploy the in-tenant runtime: the LiteLLM
  gateway (in-tenant endpoint, TN-1), self-host Langfuse (ADR-0036), the sandbox
  (ADR-0035 WS-C), and — only if a Founder decision has opened the eject-path — the live
  vLLM/SGLang open-weight serving backend (FR-005 flag flipped ON on that VM).
- Wire RBAC + the SIEM audit export against the tenant's real vault and SIEM (TN-3/TN-4).
- Finalize the deploy runbook; **TB-5 posture:** `ws_e_tenant_hardening` ships **OFF** —
  merging changes no dispatch behaviour; enabling on the VM is a later explicit Founder
  act, not this ticket.
- Record the deploy decision + evidence; a committed wave attestation (ADR-0031/0032).

## Acceptance criteria
- [ ] Ubuntu tenant VM provisioned; in-tenant runtime (gateway/Langfuse/sandbox) deployed; every endpoint resolves in-tenant (TN-1 verified on the VM).
- [ ] RBAC + SIEM audit export wired to the tenant's real vault + SIEM (TN-3/TN-4); redaction verified on a live exported event.
- [ ] Deploy runbook complete; `ws_e_tenant_hardening` confirmed OFF at merge; a with-flag-off wave byte-identical to pre-merge (evidence recorded).
- [ ] Committed wave attestation; `diagnostics.py` 100/100; merged PR, green CI.

## Log
### 2026-07-24 — CEO
Created by /daslab-plan (WS-E Deployment, GATE-5).

**BLOCKED — external dependency (no VM).** This stage requires a REAL Linux VM / a live
self-host stack (actual deploy, and — if the eject-path is Founder-opened — live
vLLM/SGLang serving on real hardware). A DasLab agent has no VM and cannot provision or
operate live infrastructure, so this ticket is created `blocked` per the dispatch rule
(board/README.md: external-dependency blocks are never auto-dispatched). The unblock is a
Founder/SRE action: provision the Ubuntu tenant VM (+ optional GPU host for the deferred
eject-path) and hand back credentials/access, then this ticket returns to `todo`.

All the buildable substrate — RBAC/audit config, LiteLLM gateway config, the vLLM/SGLang
eject-path adapter, the guardrail chain, the promptfoo golden-set, and their tests — lands
`todo`/`done` in DAS-1580..DAS-1585 with mocked/absent backends, so the workstream makes
real progress while this deployment gate waits on the VM. GATE-5 stays open until the VM
is provisioned; DAS-1587 (Maintenance) depends on this and waits behind it.
