---
id: DAS-1599
title: WS-H Design — Founder-only RBAC and audit, approve-gate and trigger-run UX, offline and not-a-daemon
status: backlog
assignee: cto
author: ceo
dept: engineering
priority: p1
parent: DAS-1597
goal: mustaqil-ws-h-control
spec: 008-mustaqil-ws-h-control
implements: [FR-002, FR-003, FR-004, FR-007]
labels: [security]
zone: docs/design
depends_on: [DAS-1598]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 2 — Design (closes GATE-2 for WS-H).** Design the governed control model
the Development tickets implement. No code beyond schemas/specs. Accountable stage owner
= CTO; responsible = backend-em; Security Lead consulted (auth/RBAC/audit); CDO
consulted (dashboard UX).

- **RBAC + fail-closed (CP-2/FR-002):** how a request is identified to a role
  (viewer < operator < founder), where the token/identity map lives (tenant vault,
  ADR-0038 TN-5, out of the repo), and the fail-closed rule — unconfigured RBAC ⇒ 503
  for every data/action endpoint, only a health probe and a data-free HTML shell answer.
  No anonymous or default-open access; in-tenant bind only.
- **Three governed writes + audit (CP-3/FR-003):** the exact write surface — (a) submit
  a goal proposal to the Founder-approved queue, (b) trigger a run via the WS-B headless
  runner (ADR-0034), (c) approve/deny a gate or interrupt-card — each RBAC-authorized,
  each appended to the event store (ADR-0024/0025) and redacted per ADR-0012. Specify the
  audit record shape and the redaction mapping.
- **Founder-only approval (CP-3/FR-004/Q6):** the approve-gate UX and the invariant that
  approval binds to a **Founder-role identity** — the dashboard, an agent, or any
  non-Founder role cannot sign a gate; a GATE-5-open deployment stays machine-blocked
  regardless of any button. Bind to the **real** gate/interrupt-card machinery — never a
  PoC stub.
- **Board-canonical view+controller (CP-4):** every read/write goes through the board /
  goal queue / event store; no parallel dashboard state; a divergence resolves to the
  board.
- **Offline-install + NOT-a-daemon (FR-007/FR-006/CP-5/6):** the vendored-wheel offline
  install path (platform-matched closure), the degrade-to-static contract (the read
  cockpit is the base case when the process is absent), the optional Founder-enabled
  process shape (systemd/launchd opt-in), and the in-tenant/no-external-SaaS boundary.

Extends the ADR-0028 cockpit render seam (CP-1) — the design reuses `render()`/
`_render_panel`/`NODATA` + `cockpit_html.py`, never a second cockpit.

## Acceptance criteria
- [ ] Design doc under `docs/design/` covering: the RBAC + fail-closed contract, the three governed writes + audit/redaction mapping, the Founder-only approve-gate invariant bound to the real gate machinery, the board-canonical view+controller rule, and the offline-install + degrade-to-static + NOT-a-daemon design — each traced to its FR and CP invariant.
- [ ] Negative-path behaviour specified for SC-001 (fail-closed RBAC, 401, data-free shell) and SC-002 (Founder-only approval, GATE-5 stays blocked) so DAS-1603 can test it.
- [ ] The vendored-wheel offline-install and degrade-to-static contract specified so DAS-1602 can build it and DAS-1603 can test the offline boot (SC-003).
- [ ] Security Lead (auth/RBAC/audit) + CDO (UX) review recorded. `board_lint`/`check_spec_consistency`/`check_dependency_graph` green. Merged PR, green CI.

## Log
### 2026-07-24 — CEO
Created by /daslab-plan (WS-H Design). CP-2/CP-3/CP-4 + Q6 Founder-only approval + the
offline-install/NOT-a-daemon deployment reality. Bind approve-gate to the REAL gate
machinery (not the PoC stub). Security Lead + CDO consulted.
