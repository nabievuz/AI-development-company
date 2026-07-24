---
id: DAS-1580
title: WS-E Planning — ratify ADR-0038, review SPEC-006, land the ws_e_tenant_hardening key OFF
status: todo
assignee: cto
author: ceo
dept: engineering
priority: p1
parent: DAS-1579
goal: mustaqil-ws-e-tenant
spec: 006-mustaqil-ws-e-tenant
implements: [FR-004, FR-008]
labels: [governance, security]
zone: docs/adr
depends_on: [DAS-1543]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 1 — Planning (closes GATE-1 for WS-E).**

- Ratify **ADR-0038** (currently `Proposed`) → `Accepted` after **CTO sign-off**
  (RACI 3.1/3.6 — CTO accountable; Backend EM authored); Security Lead + COO consulted
  (RBAC, secrets, audit export, GATE-6 maintenance surface). Verify TN-1…TN-5 and the
  binding scope boundary (no SaaS / SOC 2 / SSO / multi-tenant) are sound and coherent
  with the in-tenant runtime BOM (production-stack mining §2) and the MODEL STANCE Q9.
- Review `docs/specs/006-mustaqil-ws-e-tenant/SPEC.md` (FR-001…FR-008, SC-001…SC-005);
  resolve any `[NEEDS CLARIFICATION]`; mark SPEC Status `reviewed`.
- Land the WS-E feature key in `config/features.yaml` DEFAULT **OFF**
  (`ws_e_tenant_hardening`, from the DAS-1543 scaffold) — the flag that guards the whole
  hardening surface (FR-008). Confirm the DEFERRED vLLM/SGLang eject-path flag posture
  (FR-005) is captured as its own OFF sub-flag, not the near-term build.

No hardening is built in this stage — this fixes the contract the WS-E code builds against.

## Acceptance criteria
- [ ] ADR-0038 Status flipped to `Accepted` with the CTO sign-off recorded; `docs/adr/README.md` consistent; Security Lead + COO consult captured.
- [ ] SPEC-006 reviewed (Status `reviewed`), no unresolved clarification markers; FR/SC ↔ TN-1…TN-5 + BOM traceability confirmed.
- [ ] `ws_e_tenant_hardening` key present in `config/features.yaml`, value `false`, with a consumer/flip comment (confirmed from DAS-1543 — not re-added); the DEFERRED eject-path flag posture (FR-005 OFF) noted.
- [ ] `check_spec_consistency`/`check_dependency_graph`/`check_links`/`board_lint` green. (Doc/governance ticket, LOCAL-ONLY — no PR/CI exists; exempt from the merged-PR done-gate, accepted on local green.)

## Log
### 2026-07-24 — CEO
Created by /daslab-plan (WS-E Planning). Ratifies ADR-0038; reviews SPEC-006; lands the `ws_e_tenant_hardening` key OFF (from the DAS-1543 scaffold).
