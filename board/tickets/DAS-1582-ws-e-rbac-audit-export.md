---
id: DAS-1582
title: WS-E Development — RBAC Founder-only approval plus team read-only audit and SIEM export
status: todo
assignee: backend-em
author: ceo
dept: engineering
priority: p1
parent: DAS-1579
goal: mustaqil-ws-e-tenant
spec: 006-mustaqil-ws-e-tenant
implements: [FR-001, FR-002, FR-003]
labels: [security]
zone: config/rbac
depends_on: [DAS-1581]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 3 — Development (closes GATE-3 for WS-E, part 1).** Build the RBAC + audit
hardening per the DAS-1581 design. Security Lead consulted.

- **TN-3 / FR-001 (RBAC, Q6):** implement the principal/role/permission model — a
  Founder-identity principal is the ONLY actor who can approve an AADL gate; an agent
  identity can never hold gate-approval authority (structural, fail-closed — an
  unknown/agent principal denies); a non-Founder actor's approval string is refused. A
  small team holds **read-only audit** — read the trail; approve/trigger/mutate nothing.
  Every never-auto-approve category (QONUN-5) maps to the human-only Founder role.
- **TN-4 / FR-002 (audit export):** a read-only exporter of the event store +
  attestation (ADR-0024/0025/0031/0032) to the tenant SIEM as OTel/JSON, redacted per
  ADR-0012; the export is one-way (never writes back to the board) and carries no
  source/IP.
- **TN-5 / FR-003 (secrets/egress):** secrets resolved from the tenant vault (never in
  repo or spans — gitleaks + ADR-0012); egress bounded by the tenant-boundary allow-list
  (reuse the WS-A `config/egress-allowlist.yaml` posture, do not fork).
- **FR-008:** guarded by `ws_e_tenant_hardening` (OFF); with the flag OFF the surface is
  inert and dispatch is unchanged.

Hand the matching negative tests (SC-001/SC-002) to DAS-1585.

## Acceptance criteria
- [ ] RBAC model enforced: Founder-identity-only gate approval (agent/non-Founder refused, fail-closed); team read-only audit cannot approve/trigger/mutate (SC-001).
- [ ] Read-only SIEM exporter emits redacted OTel/JSON (ADR-0012); one-way, no board write-back, no code/IP (SC-002).
- [ ] Secrets from the tenant vault (never repo/spans); egress bounded by the boundary allow-list (no fork of the WS-A profile).
- [ ] Feature flag OFF by default; flag-off behaviour byte-identical to pre-merge; `diagnostics.py` 100/100. Merged PR, green CI.

## Log
### 2026-07-24 — CEO
Created by /daslab-plan (WS-E Development, part 1). TN-3 RBAC (Founder-only approval + team read-only audit, Q6) + TN-4 SIEM audit export + TN-5 secrets/egress; all behind `ws_e_tenant_hardening` OFF.
