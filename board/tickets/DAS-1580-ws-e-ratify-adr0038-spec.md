---
id: DAS-1580
title: WS-E Planning — ratify ADR-0038, review SPEC-006, land the ws_e_tenant_hardening key OFF
status: done
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
- [x] ADR-0038 Status flipped to `Accepted` with the CTO sign-off recorded; `docs/adr/README.md` consistent; Security Lead + COO consult captured.
- [x] SPEC-006 reviewed (Status `reviewed`), no unresolved clarification markers; FR/SC ↔ TN-1…TN-5 + BOM traceability confirmed.
- [x] `ws_e_tenant_hardening` key present in `config/features.yaml`, value `false`, with a consumer/flip comment (confirmed from DAS-1543 — not re-added); the DEFERRED eject-path flag posture (FR-005 OFF) noted.
- [x] `check_spec_consistency`/`check_dependency_graph`/`check_links`/`board_lint` green. (Doc/governance ticket, LOCAL-ONLY — no PR/CI exists; exempt from the merged-PR done-gate, accepted on local green.)

## Log
### 2026-07-24 — CEO
Created by /daslab-plan (WS-E Planning). Ratifies ADR-0038; reviews SPEC-006; lands the `ws_e_tenant_hardening` key OFF (from the DAS-1543 scaffold).

### 2026-07-24 — CTO
**AADL Stage-1 Planning gate (GATE-1) CLOSED for WS-E TENANT. LOCAL-ONLY — no branch/PR/push (doc-governance ticket).**

**1. ADR-0038 ratified `Proposed` → `Accepted`** (CTO RACI 3.1/3.6 A; Security Lead + COO consult captured in the sign-off). Judged sound against the Founder discovery answers and the in-tenant runtime BOM (production-stack mining §2):
- **TN-1 in-tenant boundary — ENFORCED.** `check_in_tenant.py` (DAS-1543) fails any code/IP endpoint that resolves external except the ONE accepted proprietary exception, the Claude subscription model call (Q9). During ratification I added a coherence clarification to TN-1 naming that exception explicitly (it previously read as an absolute "nothing leaves the tenant," which mismatched the guard's `accepted_external_roles` carve-out and SPEC-006 FR-004). Not a blocking defect — a well-governed accepted exception — fixed in place as a ratification refinement.
- **vLLM/SGLang DEFERRED — CONFIRMED.** The open-weight in-tenant inference path is a deferred, flag-OFF eject-path (SPEC-006 FR-005), NOT the near-term build; near-term default stays the Claude subscription via LiteLLM gateway (FR-004, ADR-0009 admission layer). No non-in-tenant model/inference path carrying code/IP was found.
- **Non-goals BINDING — CONFIRMED.** SOC 2 / SSO-SAML-SCIM / multi-tenant isolation / billing are explicit + binding out-of-scope (Q10); a PR adding them is rejected under the ADR boundary. No SaaS/multi-tenant scope creep found.
- **RBAC (Q6) — SOUND.** TN-3 maps the org + Founder gate onto real access control: Founder-identity-only gate approval, team read-only audit, agent identity can never approve (QONUN-5 human-only). `docs/adr/README.md` row 0038 updated to Accepted.

**2. SPEC-006 reviewed `draft` → `reviewed`.** FR-001…FR-008 ↔ SC-001…SC-005 ↔ TN-1…TN-5 + BOM traceability confirmed and testable (each SC is a negative/probe test): FR-001→SC-001 (RBAC), FR-002/003→SC-002 (audit export + redaction), FR-004/005→SC-003 (in-tenant gateway + deferred eject-path inert), FR-006/007→SC-004 (guardrails + golden-set evals), FR-008→SC-005 (flag-OFF byte-identical dispatch + Q10 boundary). No `[NEEDS CLARIFICATION]` markers. Status line only edited — no FR-/SC- id tokens added.

**3. `ws_e_tenant_hardening` — CONFIRMED present OFF** in `config/features.yaml` line 24 (`false`, with consumer/flip comment, from DAS-1543 — not re-added). The FR-005 DEFERRED vLLM/SGLang eject-path is captured in the SPEC as its own OFF sub-flag to be created at Development (build-time artifact, not near-term); no sub-flag added now (correct at Planning; also outside this ticket's touch scope).

**Validators (all exit 0):** `check_spec_consistency` OK (10 SPECs), `check_links` OK, `board_lint` OK (180 tickets, 0 violations; the lone WARN is pre-existing on DAS-1507, unrelated).

**Files touched (LOCAL-ONLY):** `docs/adr/0038-enterprise-internal-self-host-hardening.md`, `docs/adr/README.md`, `docs/specs/006-mustaqil-ws-e-tenant/SPEC.md`, this ticket. No genuine defect to route — no rubber-stamp: the TN-1 exception mismatch was corrected in place. **Unblocks DAS-1581 (WS-E Design).** DAS-1586 (deploy to a real VM) remains BLOCKED as expected — does not affect this Planning gate. Ticket → `done`.
