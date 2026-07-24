---
id: DAS-1581
title: WS-E Design — RBAC model, audit export, and in-tenant runtime BOM wiring
status: todo
assignee: backend-em
author: ceo
dept: engineering
priority: p1
parent: DAS-1579
goal: mustaqil-ws-e-tenant
spec: 006-mustaqil-ws-e-tenant
implements: [FR-001, FR-002, FR-003, FR-006]
labels: [security]
zone: docs/design
depends_on: [DAS-1580]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 2 — Design (closes GATE-2 for WS-E).** Design the hardening model the
Development tickets implement. No code beyond schemas/specs. Security Lead + COO
consulted (accountable stage owner = CTO; responsible = backend-em).

- **RBAC model (TN-3 / FR-001 / Q6):** how the 32-role org + Founder gate map onto real
  access control — which principal may approve which AADL gate, trigger a run
  (`/daslab-run`, ADR-0034), and read the audit; every never-auto-approve category
  (QONUN-5) → a human-only Founder-identity role; an agent identity can NEVER hold
  gate-approval authority; a small team holds **read-only audit** (read the trail;
  approve/trigger/mutate nothing). Approval is a Founder-identity RBAC event, never a
  chat string or an agent's own output.
- **Audit export (TN-4 / FR-002):** how the event store + attestation
  (ADR-0024/0025/0031/0032) export read-only to the tenant SIEM as OTel/JSON, redacted
  per ADR-0012 — no code/IP leaves, never a write path back into the board.
- **Secrets / egress (TN-5 / FR-003):** secrets in the tenant vault (never repo/spans),
  egress allow-list at the tenant boundary (reuse WS-A `config/egress-allowlist.yaml`
  posture, do not fork); the browser tool (ADR-0033 TB-4) as untrusted egress.
- **In-tenant runtime BOM wiring:** how the LiteLLM **gateway** (FR-004) realizes the
  ADR-0009 admission layer + the TN-1 in-tenant precondition (DAS-1543); where the
  **vLLM/SGLang** DEFERRED eject-path adapter sits behind its own OFF flag (FR-005); how
  the **Presidio+classifier+policy** guardrail chain (FR-006) binds to the ADR-0012
  redaction path and is admitted through the ADR-0033 edge; how **promptfoo** + a
  hand-labeled golden set (FR-007) wires into the existing `evals/` CI path
  (golden-set-before-LLM-judge + anti-gaming probe). Each element traced to its FR + TN
  invariant, all behind `ws_e_tenant_hardening` OFF.

## Acceptance criteria
- [ ] Design doc under `docs/design/` covering: the RBAC principal/role/permission model + Founder-gate mapping, the SIEM audit-export contract, the secrets/egress policy, and the BOM wiring (gateway, deferred eject-path, guardrail chain, evals) — each traced to its FR and TN invariant.
- [ ] Negative-path behaviour specified for SC-001/SC-002/SC-003/SC-004 (agent/non-Founder approval refused, read-only-audit cannot mutate, export redaction, external-endpoint BLOCK, guardrail probe) so DAS-1585 can test it.
- [ ] Non-goals restated (no SaaS/SOC2/SSO/multi-tenant — ADR-0038 boundary) with the review rule that such a change is rejected.
- [ ] Security Lead + COO review recorded. `board_lint`/`check_spec_consistency`/`check_dependency_graph` green. Merged PR, green CI.

## Log
### 2026-07-24 — CEO
Created by /daslab-plan (WS-E Design). RBAC (TN-3/Q6) + audit export (TN-4) + secrets/egress (TN-5) + in-tenant runtime BOM wiring (gateway/eject-path/guardrails/evals) admission model.
