---
id: DAS-1583
title: WS-E Development — in-tenant LiteLLM model gateway plus deferred vLLM SGLang eject-path adapter
status: todo
assignee: backend-eng-1
author: ceo
dept: engineering
priority: p1
parent: DAS-1579
goal: mustaqil-ws-e-tenant
spec: 006-mustaqil-ws-e-tenant
implements: [FR-004, FR-005]
labels: [security]
zone: tools/model_gateway
depends_on: [DAS-1581]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 3 — Development (closes GATE-3 for WS-E, part 2).** Build the in-tenant
model gateway per the DAS-1581 design. Distinct repo zone from DAS-1582 so the two
Development tickets proceed without a same-zone wave collision.

- **TN-1 / FR-004 (gateway):** a **LiteLLM** in-tenant model gateway config that realizes
  the ADR-0009 admission layer — every model call resolves to an **in-tenant endpoint**;
  the near-term default is the Claude subscription via account auth (Q9, NOT a metered
  API key); the auth path stays swappable. A model call whose endpoint resolves to a
  hosted/external target that carries code/IP is a config error that **BLOCKS** the run
  (TN-1 precondition, built on DAS-1543). Budget/credit ceiling stays the outer bound
  (ADR-0027 SI-5) — not re-implemented here, only respected.
- **FR-005 (DEFERRED eject-path):** a vLLM / SGLang open-weight in-tenant serving
  **adapter behind its own feature flag DEFAULT OFF** — the eject-path for a tenant whose
  policy forbids any external model call. It is NOT the near-term build: the adapter +
  its **unit tests are buildable with NO live serving stack present** (mock/absent
  backend); the flag stays OFF until an explicit Founder decision opens the eject-path.
  Live vLLM/SGLang serving against a real GPU/VM is out of this ticket (see the BLOCKED
  Deployment ticket DAS-1586).
- **FR-008:** guarded by `ws_e_tenant_hardening` (OFF); the eject-path additionally
  behind its own OFF sub-flag; flag-off ⇒ inert, dispatch unchanged.

Hand the matching negative tests (SC-003) to DAS-1585.

## Acceptance criteria
- [ ] LiteLLM gateway config resolves every model call to an in-tenant endpoint; default = Claude subscription via account auth (Q9); the auth path is swappable via the admission layer.
- [ ] An external/hosted code-IP-carrying endpoint evaluates to a BLOCKED config error (TN-1); a negative test proves it (SC-003).
- [ ] vLLM/SGLang eject-path adapter present behind its own DEFERRED flag OFF; unit-tested with no live serving stack; inert until a Founder decision (SC-003).
- [ ] Feature flag(s) OFF by default; flag-off behaviour byte-identical to pre-merge; `diagnostics.py` 100/100. Merged PR, green CI.

## Log
### 2026-07-24 — CEO
Created by /daslab-plan (WS-E Development, part 2). TN-1/FR-004 LiteLLM in-tenant gateway (Claude-subscription default, Q9) + FR-005 DEFERRED vLLM/SGLang eject-path adapter behind its own OFF flag — adapter + unit tests buildable without a live serving stack; live serving deferred to the BLOCKED DAS-1586. All behind `ws_e_tenant_hardening` OFF.
