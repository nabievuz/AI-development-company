---
id: DAS-1603
title: WS-H Testing — RBAC deny and fail-closed, Founder-only approval, audit, offline-install boot
status: backlog
assignee: qa-eng
author: ceo
dept: engineering
priority: p1
parent: DAS-1597
goal: mustaqil-ws-h-control
spec: 008-mustaqil-ws-h-control
implements: [SC-001, SC-002, SC-003]
labels: [security]
zone: tests
depends_on: [DAS-1601, DAS-1602]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 4 — Testing (closes GATE-4 for WS-H).** Prove the governance holds with
adversarial negative tests. Security Engineer (red team) consulted.

Cover:
- **SC-001 (fail-closed RBAC):** unconfigured RBAC ⇒ 503 on every data/action endpoint
  (only `/healthz` + the data-free HTML shell answer); a missing/invalid token ⇒ 401;
  the HTML shell leaks no board data without a token.
- **SC-002 (Founder-only approval):** a non-Founder role (viewer/operator) that attempts
  to approve/deny a gate is refused with an **audited deny**; only a Founder-role
  identity can approve; a **GATE-5-open deployment stays machine-blocked** regardless of
  any dashboard action.
- **SC-003 (offline install + audit):** the vendored wheel bundle installs and the app
  boots with **no network** and answers `/healthz`; every governed write appends a
  redacted audit record (ADR-0012).
- **SC-004 guard:** with the flag OFF, dispatch is byte-identical to pre-merge; with the
  optional process absent, the surface degrades to the static cockpit.
- Fold in and extend `tests/test_ws_h_control_plane.py` (the 7-test spike suite).

## Acceptance criteria
- [ ] Negative tests exist and PASS in CI for SC-001 (503 fail-closed, 401, data-free shell), SC-002 (non-Founder approval denied + audited; GATE-5 stays blocked), and SC-003 (offline boot + redacted audit).
- [ ] Flag-off / process-absent degrade-to-static behaviour asserted (SC-004 guard).
- [ ] `tests/test_ws_h_control_plane.py` folded in and green; overall pytest green in CI.
- [ ] Security Engineer red-team review recorded. Merged PR, green CI.

## Log
### 2026-07-24 — CEO
Created by /daslab-plan (WS-H Testing). SC-001 fail-closed RBAC + SC-002 Founder-only
approval (GATE-5 stays blocked) + SC-003 offline-install boot + audit; red-team consulted.
Depends on both DAS-1601 (approve-gate/trigger-run) and DAS-1602 (offline install).
