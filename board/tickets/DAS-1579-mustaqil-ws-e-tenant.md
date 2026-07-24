---
id: DAS-1579
title: MUSTAQIL WS-E TENANT — enterprise-internal self-host hardening plus in-tenant runtime BOM (EPIC)
status: backlog
assignee: cto
author: ceo
dept: engineering
priority: p1
parent: 
goal: mustaqil-ws-e-tenant
spec: 006-mustaqil-ws-e-tenant
labels: [security]
depends_on: [DAS-1543]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**EPIC — MUSTAQIL v3.0 WS-E TENANT.** Harden DasLab for the enterprise model that
matches its identity: a company runs the whole stack **on its own infrastructure** to
build its own software, with code and IP staying **in-tenant**. This is a self-host
hardening target — RBAC (Founder-only approval + team read-only audit), audit-export,
in-tenant secrets/egress — **plus the in-tenant runtime BOM**: LiteLLM gateway ·
vLLM/SGLang in-tenant inference (a DEFERRED eject-path) · Presidio+classifier+policy
guardrails · promptfoo+golden-set evals.

**Contract of record:** ADR-0038 (TN-1…TN-5 + the binding scope boundary),
`docs/specs/006-mustaqil-ws-e-tenant/SPEC.md` (FR-001…FR-008, SC-001…SC-005), the
in-tenant runtime BOM (production-stack mining §2), Master Prompt v3.0 (TN-1 in-tenant
precondition, MODEL STANCE Q9), discovery Q6 (Founder-only approval + team read-only
audit), Q9 (Claude subscription default; open-weight serving a DEFERRED eject-path),
Q10 (internal self-host ONLY).

**TN-1 in-tenant precondition (built in DAS-1543).** The whole stack — sandbox,
Langfuse, tool bridges, AND the model gateway — must resolve to in-tenant endpoints;
any hosted/external endpoint that carries code/IP is a config error that BLOCKS the
run. WS-E's model gateway (FR-004) is bound to this precondition.

**Non-goals (binding — ADR-0038 scope boundary, Q10):** NO SaaS packaging, NO SOC 2
certification, NO SSO / SAML / SCIM, NO multi-tenant isolation, NO billing. A PR that
adds any of these under this workstream is out of scope and rejected — that work needs
its own funded program and ADR. This is internal self-host, and **no**.

**Sequence.** Per the v3.0 map, WS-E **overlaps WS-C** (LOOP) and lands after WS-B
(RUNNER); a workstream may not skip its predecessor's AADL gate. The WS-C overlap is a
scheduling relationship, not a hard ticket dependency, so it is noted here and NOT
encoded as a `depends_on` (no dangling refs). This epic depends only on the prep
bootstrap DAS-1543 (TN-1 precondition + `ws_e_tenant_hardening` scaffold).

**MODEL STANCE (Q9, binding precondition).** DasLab runs on a Claude subscription via
the ADR-0034 Agent-SDK runner with account auth (NOT a metered API key). The in-tenant
gateway (FR-004) keeps the auth path swappable; the open-weight vLLM/SGLang serving path
(FR-005) is a **DEFERRED eject-path behind its own flag OFF**, not the near-term build.

**Deployment reality (external dependency).** The Deployment stage (DAS-1586) requires a
REAL Linux VM / a live self-host stack (actual deploy, live vLLM/SGLang serving) — an
agent has no VM, so that ticket is created `blocked` with an external-dependency note.
The config / policy / adapter code + their tests remain buildable `todo` in the earlier
stages so the workstream still makes real progress.

**AADL — six-stage closure (children DAS-1580..DAS-1587):**

| Child | Stage | Ticket | Owner-hint |
|---|---|---|---|
| DAS-1580 | Planning | Ratify ADR-0038 + review SPEC-006 + land the `ws_e_tenant_hardening` key OFF | cto |
| DAS-1581 | Design | RBAC model (TN-3, Q6), audit export (TN-4), in-tenant runtime BOM wiring (gateway/guardrails/evals) | backend-em |
| DAS-1582 | Development | RBAC Founder-only approval + team read-only audit (TN-3), audit export to SIEM (TN-4), in-tenant secrets/egress (TN-5) | backend-em |
| DAS-1583 | Development | In-tenant model gateway (LiteLLM, TN-1/FR-004) + vLLM/SGLang eject-path adapter behind a DEFERRED flag (FR-005) | backend-eng-1 |
| DAS-1584 | Development | Presidio+classifier+policy guardrails (TN-5/FR-006) + promptfoo golden-set evals (FR-007), each via the 0033 edge | backend-eng-2 |
| DAS-1585 | Testing | Negative/RBAC/egress/guardrail/eval tests (SC-001…SC-004) | qa-eng |
| DAS-1586 | Deployment | BLOCKED — real Linux VM / live self-host stack (actual deploy, live vLLM/SGLang) | sre-eng |
| DAS-1587 | Maintenance | Scheduled health/eval of the tenant hardening surface (RBAC drift, redaction/guardrail probe) | product-analyst |

## Acceptance criteria
- [ ] All eight children (DAS-1580..DAS-1587) closed, each through its own AADL stage gate (DAS-1586 stays `blocked` until a real VM is provisioned — a sanctioned external-dependency stall, not a failure).
- [ ] **FR-001/TN-3 + Q6:** RBAC maps Founder-only gate approval (agent identity can never approve) + team read-only audit; a negative test proves it (SC-001).
- [ ] **FR-002/TN-4:** event store + attestation exportable read-only to the tenant SIEM as redacted OTel/JSON; a redaction probe over an exported event passes (SC-002).
- [ ] **FR-003/TN-5:** secrets in the tenant vault (never repo/spans), egress allow-list at the boundary.
- [ ] **FR-004/TN-1:** the LiteLLM in-tenant gateway resolves every model call to an in-tenant endpoint (default = Claude subscription, Q9); an external code/IP-carrying endpoint BLOCKS the run (SC-003).
- [ ] **FR-005/Q9:** the vLLM/SGLang open-weight serving path is a DEFERRED eject-path adapter behind its own flag OFF — buildable + unit-tested with no live serving stack, inert until a Founder decision (SC-003).
- [ ] **FR-006/TN-5:** Presidio+classifier+policy guardrail chain wired via the 0033 edge; a guardrail probe detects + redacts planted PII/secrets (SC-004).
- [ ] **FR-007:** promptfoo golden set checked before any LLM-judge, with an anti-gaming probe (SC-004); no golden-set pass ⇒ not green.
- [ ] **FR-008:** the whole surface behind `ws_e_tenant_hardening` OFF; flag-OFF dispatch byte-identical to pre-merge (SC-005). Non-goals (SaaS/SOC2/SSO/multi-tenant) rejected.
- [ ] `diagnostics.py` 100/100; `board_lint`/`check_spec_consistency`/`check_dependency_graph`/validators green; no `project:` field on any WS-E ticket (R9); committed wave attestation (ADR-0031/0032).
- [ ] **Epic acceptance = AADL 6-gate closure for WS-E**, each gate logged in the stage-board.

## Log
### 2026-07-24 — CEO
Created by /daslab-plan from the Founder-approved MUSTAQIL v3.0 queue (WS-E TENANT).
Contract = ADR-0038 (TN-1..TN-5) + SPEC-006 (FR-001..FR-008, SC-001..SC-005) + the
in-tenant runtime BOM (production-stack mining §2). Children DAS-1580..DAS-1587 (one per
AADL stage, 3 Development for RBAC/audit · gateway+eject-path · guardrails+evals).
Deployment (DAS-1586) created `blocked` — needs a real Linux VM / live self-host stack an
agent cannot provision; the config/policy/adapter code + tests stay buildable `todo` in
the earlier stages. Sequence overlaps WS-C (noted, not a `depends_on`). Depends on the
prep bootstrap DAS-1543 for the TN-1 in-tenant precondition + the `ws_e_tenant_hardening`
scaffold. Org-engine epic — no `project:` field (board_lint R9).
