---
id: DAS-1581
title: WS-E Design — RBAC model, audit export, and in-tenant runtime BOM wiring
status: done
assignee: cto
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
updated: 2026-07-25  # GATE-2 closed by CTO
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

### 2026-07-25 — Backend EM
**AADL Stage-2 Design (GATE-2) complete.** Wrote the design doc
`docs/design/ws-e-tenant-hardening.md` (mirrors the WS-A/WS-D design-doc style), each
element traced to its FR + TN invariant, all behind `ws_e_tenant_hardening` OFF.

Design summary:
- **RBAC (TN-3/FR-001/Q6):** model lives in a tracked SSOT `config/rbac.yaml`
  (`security_sensitive`+`governance_or_policy`+`permission_change`, never `approval:
  auto*`). Three principal kinds — `founder` (human), `audit-team` (human, read-only),
  `agent` (role subagent), plus the `orchestrator` mechanism — over a permission matrix.
  **`gate.approve` and `config.edit.security` are Founder-identity ONLY**; an `agent`
  principal is **structurally excluded** (the permission is absent from the kind — the
  evaluator `decide(agent, gate.approve)` returns deny by construction, QONUN-5
  human-only). The FR-001 crux: **approval is an attributed Founder-identity EVENT**
  (`gate_approval` `{principal_kind: founder, …}`, principal id stamped by the runtime /
  ADR-0039 control-plane session — NOT by agent output); the `approval: human:founder`
  frontmatter string is an unverified **claim** that closes a never-auto-approve gate
  only when backed by a matching Founder-identity event — a forged string with no backing
  event is rejected.
- **Audit trail + SIEM export (TN-4/FR-002):** append-only, attributed event store
  (ADR-0024/0025) + attestation (ADR-0031/0032), with a new `gate_approval` event class
  (Tier-M by construction — no secret field). Export is a **read-only, one-way** OTel/JSON
  SIEM shim (WS-D read-side posture) — no write path back into the board; ADR-0012
  redaction at write **and** again at the boundary (reuse the shared scrubber).
- **Secrets/egress (TN-5/FR-003):** secrets in the tenant vault, fact-of-use-only events;
  egress reuses WS-A `config/egress-allowlist.yaml` verbatim (no fork); browser/computer-use
  = untrusted egress (ADR-0033 TB-4).
- **In-tenant runtime BOM (TN-1/FR-004-007):** the **LiteLLM in-tenant gateway** realizes
  the ADR-0009 admission layer on the **ADR-0034 SDK runner** — the seam that actually owns
  the transport (honest reconciliation with ADR-0009's harness=admission-not-proxy finding);
  default model = Claude subscription over account auth (Q9), the sole
  `accepted_external_roles` exception, swappable auth. The **vLLM/SGLang eject-path is a
  DEFERRED adapter behind its own sub-flag `ws_e_openweight_ejectpath` OFF** — buildable +
  unit-tested with **no live serving stack** (mock endpoint), in-tenant (strengthens TN-1),
  NOT near-term. **Presidio+classifier+policy** guardrail chain complements the ADR-0012 §2
  scrubber and enters via the ADR-0033 governed MCP edge (Presidio's own I/O scrubbed).
  **promptfoo** golden-set-before-LLM-judge + anti-gaming probe into the existing `evals/` CI
  path. All code/IP endpoints in-tenant, enforced fail-closed by the landed
  `check_in_tenant.py` (reused, no parallel check).
- **Non-goals (FR-008/Q10):** SaaS / SOC 2 / SSO-SAML-SCIM / multi-tenant / billing are
  **binding** out-of-scope; a PR adding any is rejected. Design verified to introduce none.

**Negative-path spec for DAS-1585** (`tests/test_ws_e_tenant_hardening.py`, §6):
- **SC-001 (RBAC deny):** `decide(agent:<any-role>, gate.approve)`=deny for every role;
  non-Founder/`audit-team` refused (read-only proven); only `founder` approves; a forged
  `approval: human:founder` with no backing Founder-identity event leaves the gate NOT
  closed; an agent cannot emit a `gate_approval` stamped `principal_kind: founder`.
- **SC-002 (audit completeness + redaction + read-only export):** export is OTel/JSON with
  no write-back path; redaction probe (`sk-ant-…`/Bearer-JWT/`postgres://…`/PRIVATE KEY/PII)
  leaves no raw substring, fail-closed, no over-redaction of Tier-M ids; exactly one
  append-only `gate_approval` record per approval, no secret field.
- **SC-003 (in-tenant block):** a hosted code/IP endpoint → `check_in_tenant.py` exit 1
  BLOCK; model call the sole accepted exception; gateway otherwise routes in-tenant;
  eject-path inert behind its deferred flag OFF (mock endpoint).
- **SC-004 (guardrail trip + eval-gate skip):** planted PII+secret detected+redacted by the
  Presidio chain (its own I/O scrubbed); a Presidio call by an undeclared role denied by the
  same `decide()`; promptfoo golden-set runs before any judge, no golden-set pass ⇒ RED,
  anti-gaming probe fails a test-gaming model.
- **SC-005 (flag OFF byte-identical):** noted for completeness — `ws_e_tenant_hardening` OFF
  ⇒ byte-identical dispatch.

Development mapping: **DAS-1582** (RBAC+audit+SIEM export), **DAS-1583** (LiteLLM gateway +
deferred vLLM/SGLang eject-path adapter), **DAS-1584** (Presidio guardrails + promptfoo
golden-set). **DAS-1586** is a deploy **runbook** (flag OFF) — the real VM stand-up is a
Founder act; runbook + flag-OFF ship closes GATE-5 on local-green (prior-workstream pattern).

Validators: `python3 scripts/board_lint.py` exit 0 (OK, 0 violations — the lone WARN is
pre-existing DAS-1507, unrelated); `python3 scripts/check_links.py` exit 0;
`python3 scripts/check_spec_consistency.py` exit 0; `python3 scripts/check_dependency_graph.py`
exit 0. Touched ONLY `docs/design/ws-e-tenant-hardening.md` + this ticket. LOCAL-ONLY — no
git push / PR / commit / remote.

**Status → `in_review`; assignee → `cto`** (GATE-2 accountable; Security Lead + COO consulted
per ADR-0038 RACI). Escalation: none — the design fits within charter (technical decisions,
ADR-documented). Routing note for the orchestrator: reviewer = CTO; Security Lead should be
consulted on §1 RBAC + §2 redaction + §3 secrets/egress, COO on the §8 GATE-6 maintenance
surface (DAS-1587).

### 2026-07-25 — CTO — GATE-2 CLOSED (Design ratified)
**AADL Stage-2 / GATE-2 (Design) CLOSED for WS-E TENANT.** Reviewed
`docs/design/ws-e-tenant-hardening.md` against Accepted ADR-0038 (TN-1..TN-5 + the
binding scope boundary — CTO-ratified 2026-07-24), SPEC-006 (FR-001..008 / SC-001..005),
ADR-0009 (admission), ADR-0012 (redaction), ADR-0033 (governed tool edge), and Founder
answers Q6/Q9/Q10. Carried the **Security-Lead consulted** review myself (§1 RBAC, §2
redaction, §3 secrets/egress + in-tenant boundary). Design **RATIFIED** — no defect found.

Judgment (each axis sound):
- **§1 RBAC (Founder-identity-only) — the FR-001 crux holds.** `config/rbac.yaml` SSOT;
  `gate.approve` + `config.edit.security` are Founder-identity ONLY. Agent exclusion is
  **STRUCTURAL, not advisory** (CRITICAL CHECK (b) satisfied): the permission is *absent*
  from the `agent` kind, so `decide(agent, gate.approve)` returns deny by construction —
  the same "structurally unrepresentable" pattern as the ADR-0026 route-graph and the WS-A
  tool-allowlist. Approval is an **attributed `gate_approval` EVENT** whose `principal_id`
  is stamped by the runtime / ADR-0039 control-plane session, never by agent output; the
  `approval: human:founder` frontmatter string is an unverified **CLAIM** that closes a
  never-auto-approve gate ONLY when backed by a matching Founder-identity event — a forged
  string with no backing event is rejected (QONUN-5). An agent cannot emit a `gate_approval`
  stamped `principal_kind: founder` (the write is refused). Double-lock preserved:
  `check_never_auto_approve.py` at the ticket layer + the RBAC event-backing at the gate.
- **§2 audit / redaction — holds.** Append-only attributed store (ADR-0024/0025) + new
  `gate_approval` class (Tier-M by construction, no secret field) + attestation
  (ADR-0031/0032). SIEM export is **read-only, one-way** OTel/JSON (WS-D read-side posture)
  with **no write path back** into `board/.events.jsonl`, a ticket, an attestation, or
  SIEM-as-source — event store stays system-of-record (ADR-0025/C2). ADR-0012 redaction at
  write AND again at the boundary, reusing the **same** scrubber (no third redactor).
- **§3 secrets / egress + in-tenant boundary — holds.** Secrets in the tenant vault,
  fact-of-use-only Tier-M events; egress **reuses** WS-A `config/egress-allowlist.yaml`
  verbatim (no fork); browser/computer-use = untrusted egress (ADR-0033 TB-4). TN-1
  verified against the landed `config/tenant_boundary.yaml`: `claude_model` (`role: model`,
  api.anthropic.com) is the SOLE `carries_code_ip: true` external endpoint (the accepted Q9
  exception); every other code/IP endpoint in-tenant, fail-closed by the landed
  `check_in_tenant.py` (reused, no parallel check). The vLLM/SGLang eject-path is DEFERRED
  behind its own sub-flag `ws_e_openweight_ejectpath` OFF — buildable/unit-tested with no
  live serving stack (mock endpoint), in-tenant (strengthens TN-1).
- **Non-goals CLEAN (CRITICAL CHECK (a) satisfied).** §5 restates the binding non-goals
  (SaaS / SOC 2 / SSO-SAML-SCIM / multi-tenant isolation / billing) with the reject-on-sight
  review rule, matching ADR-0038's binding scope boundary. Design introduces **none**: §1 is
  a local principal config file (not identity federation), §2 export is one-way audit egress
  (not billing/metering), and there is no tenant-isolation/SaaS surface in §1–§4. No scope
  creep.
- **Negative-path spec (§6) ACCEPTED for DAS-1585.** SC-001 (RBAC deny + forged-approval
  rejected + agent-cannot-emit-founder-event), SC-002 (audit completeness + redaction +
  read-only export), SC-003 (in-tenant BLOCK, model sole exception, eject-path inert),
  SC-004 (guardrail trip + eval-gate skip), SC-005 (flag-OFF byte-identical) — all directly
  expressible against the DAS-1582/1583/1584 surfaces, the reused ADR-0033 hook, the ADR-0012
  scrubber, and the landed `check_in_tenant.py` + `tenant_boundary.yaml`.
- **ADR-0009 reconciliation honest.** The LiteLLM gateway is placed on the ADR-0034 SDK
  runner that actually owns the transport (not claimed as a harness transport proxy) — a
  genuine reconciliation, not hand-waving.

Acceptance criteria: all four satisfied (design doc traced FR↔TN; negative-path for
SC-001..004; non-goals + reject rule; Security-Lead review carried here, COO GATE-6 surface
deferred to DAS-1587). "Merged PR / green CI" is the deploy concern (GATE-5/DAS-1586,
Founder VM act) — per the prior-workstream local-green pattern and this dispatch, GATE-2
closes on local-green.

Validators (exact): `python3 scripts/board_lint.py` exit 0 (OK, 180 tickets, 0 violations —
lone WARN is pre-existing DAS-1507, unrelated); `python3 scripts/check_links.py` exit 0;
`python3 scripts/check_spec_consistency.py` exit 0 (10 SPEC.md checked). Foundations
verified landed: `scripts/check_in_tenant.py`, `config/tenant_boundary.yaml`
(role:model + role:audit), `config/egress-allowlist.yaml`, `config/features.yaml:24`
`ws_e_tenant_hardening: false`, ADR-0038 **Accepted**.

**GATE-2 CLOSED → `status: done`.** This UNBLOCKS the three WS-E Development tickets —
**DAS-1582** (RBAC + audit + SIEM export, zone `config`/`rbac`), **DAS-1583** (LiteLLM
gateway + deferred vLLM/SGLang eject-path, zone `tools/model_gateway`), **DAS-1584**
(Presidio + promptfoo, zone `tools/guardrails`) — distinct zones, dispatchable in parallel.
LOCAL-ONLY: edited only this ticket file; no git push / PR / commit / remote. Escalation:
none — within CTO charter (GATE-2 accountable, technical decision, ADR-documented).
