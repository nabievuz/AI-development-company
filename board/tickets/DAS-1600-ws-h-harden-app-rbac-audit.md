---
id: DAS-1600
title: WS-H Development — harden control_plane app with ruff cleanup, Founder-only RBAC and audit
status: backlog
assignee: cto
author: ceo
dept: engineering
priority: p1
parent: DAS-1597
goal: mustaqil-ws-h-control
spec: 008-mustaqil-ws-h-control
implements: [FR-001, FR-002, FR-003]
labels: [security]
zone: tools/control_plane
depends_on: [DAS-1599]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 3 — Development (closes GATE-3 for WS-H, part 1).** Harden the on-branch
control-plane spike into a governed, CI-passing core per the DAS-1599 design.

- **Fold in the spike, do not rewrite** — `tools/control_plane/app.py` (FastAPI:
  RBAC viewer<operator<founder, board read, real cockpit embed, audit tail, CP-3a goal
  proposal), `requirements-control.txt`, `tests/test_ws_h_control_plane.py`. Harden to
  the design; keep it out of core `requirements.txt` (CP-5: optional process).
- **Ruff cleanup (blocking):** clean the **10 B008 violations** in `app.py`
  (`Depends(require(...))` in argument defaults) — read the dependency from a
  module-level singleton or call it inside the function, per the ruff hint. `ruff check
  tools/control_plane/` MUST pass clean.
- **CP-1 render seam (FR-001):** the cockpit embed MUST run the REAL `scripts/cockpit.py`
  (its argparse owns defaults) and reuse the ADR-0028 render seam; degrade to an honest
  NODATA line when unavailable. No cockpit panel is re-implemented; no second cockpit.
- **CP-2 RBAC fail-closed (FR-002):** every data/action endpoint identified to a role;
  unconfigured RBAC ⇒ 503 (only `/healthz` + the data-free HTML shell answer); a
  missing/invalid token ⇒ 401. Loopback bind by default; a network bind is a deliberate
  tenant act (ADR-0038 TN-5). RBAC token map stays out of the repo (tenant vault).
- **CP-3 audit (FR-003):** the CP-3a goal-proposal write and every request/decision are
  appended to the append-only audit trail, redacted per ADR-0012; writes go through the
  board/goal-inbox only — no ticket created, nothing approved, nothing dispatched.

Approve-gate (CP-3c) and trigger-run (CP-3b) endpoints are DAS-1601 (distinct scope,
sequenced on this ticket). Offline-install + degrade-to-static packaging is DAS-1602.

## Acceptance criteria
- [ ] Spike folded in and passing (not left untracked); `tests/test_ws_h_control_plane.py` green in CI; deps kept out of core `requirements.txt`.
- [ ] `ruff check tools/control_plane/` clean — the 10 B008 violations resolved.
- [ ] CP-1: cockpit embed runs the real `scripts/cockpit.py` via the ADR-0028 render seam; honest NODATA fallback; no re-implemented panel (FR-001).
- [ ] CP-2: RBAC fail-closed (503 without RBAC), 401 on bad/missing token, data-free HTML shell, loopback default (FR-002).
- [ ] CP-3: goal-proposal write + audit trail present, redacted (ADR-0012); board-canonical, dispatches nothing (FR-003).
- [ ] `diagnostics.py` 100/100; `board_lint`/validators green. Merged PR, green CI.

## Log
### 2026-07-24 — CEO
Created by /daslab-plan (WS-H Development, part 1). Harden `tools/control_plane/app.py`;
clean the 10 ruff B008 errors; CP-1 render-seam reuse; CP-2 fail-closed RBAC; CP-3a
audited goal proposal. Approve-gate/trigger-run are DAS-1601; offline/degrade DAS-1602.
