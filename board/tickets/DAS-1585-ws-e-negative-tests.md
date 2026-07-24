---
id: DAS-1585
title: WS-E Testing — RBAC refusal, audit-export redaction, in-tenant block, guardrail and eval probes
status: todo
assignee: qa-eng
author: ceo
dept: engineering
priority: p1
parent: DAS-1579
goal: mustaqil-ws-e-tenant
spec: 006-mustaqil-ws-e-tenant
implements: [SC-001, SC-002, SC-003, SC-004]
labels: [security]
zone: tests
depends_on: [DAS-1582, DAS-1583, DAS-1584]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 4 — Testing (closes GATE-4 for WS-E).** Prove the hardening holds with
adversarial negative tests. Security Engineer (red team) consulted.

Cover:
- **SC-001 (RBAC / TN-3):** an agent identity — and any non-Founder actor — cannot approve
  any AADL gate; a read-only-audit principal cannot approve / trigger / mutate; only a
  Founder-identity principal can approve (fail-closed on an unknown/agent principal).
- **SC-002 (audit export / TN-4):** an export is read-only OTel/JSON; a redaction probe
  over an exported event passes (no secret / PII / source survives); the export cannot
  write back to the board.
- **SC-003 (gateway / TN-1 + eject-path):** a model call resolving to a hosted/external
  code-IP endpoint evaluates to a BLOCKED config error; the gateway otherwise routes to
  the in-tenant endpoint; the vLLM/SGLang eject-path stays inert behind its deferred flag
  OFF.
- **SC-004 (guardrails + evals):** a guardrail probe detects + redacts planted PII/secrets
  through the Presidio+classifier+policy chain; the promptfoo golden set passes WITH the
  anti-gaming probe.
- **Flag-off guard (SC-005):** with `ws_e_tenant_hardening` OFF, dispatch is byte-identical
  to pre-merge.

**Scope note (external dependency).** These tests run against the in-tenant CONFIG /
POLICY / ADAPTER code with mocked or absent backends (no live vLLM/SGLang serving, no real
VM) — they are fully buildable here. Any test that would require a LIVE self-host stack or
real GPU serving belongs to the BLOCKED Deployment ticket DAS-1586, not this one.

## Acceptance criteria
- [ ] Negative tests exist and PASS in CI for SC-001 (RBAC refusal), SC-002 (export redaction + no write-back), SC-003 (in-tenant BLOCK + eject-path inert), SC-004 (guardrail probe + golden-set anti-gaming).
- [ ] Flag-off no-op behaviour asserted (SC-005).
- [ ] All tests run against config/policy/adapter code with mocked/absent backends (no live stack required); overall pytest green in CI.
- [ ] Security Engineer red-team review recorded. Merged PR, green CI.

## Log
### 2026-07-24 — CEO
Created by /daslab-plan (WS-E Testing). SC-001..SC-004 negative/probe tests against config/policy/adapter code with mocked backends; red-team consulted. Live-stack tests deferred to the BLOCKED DAS-1586.
