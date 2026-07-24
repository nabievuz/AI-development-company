---
id: DAS-1602
title: WS-H Development — vendored-wheels offline install, degrade-to-static, optional Founder-enabled process
status: backlog
assignee: cto
author: ceo
dept: engineering
priority: p1
parent: DAS-1597
goal: mustaqil-ws-h-control
spec: 008-mustaqil-ws-h-control
implements: [FR-006, FR-007, FR-008]
labels: [security]
zone: tools/control_plane/install
depends_on: [DAS-1599]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 3 — Development (closes GATE-3 for WS-H, part 3).** Make the control plane
**installable on a no-network in-tenant server** and honor the NOT-a-daemon law. Distinct
repo zone (`tools/control_plane/install`) from DAS-1600/1601 so it can proceed in
parallel with the app-core work without a same-zone wave collision.

- **FR-008 offline install (vendored wheels):** ship an offline wheel-bundle install path
  — a full platform-matched dependency closure (fastapi/uvicorn/starlette/pydantic +
  their transitive deps, verified against real `Requires-Dist`, not just pip's
  cross-platform resolution which has silently dropped `exceptiongroup`). Install with
  `pip install --no-index --find-links=… --target=site-packages`, or set `PYTHONPATH` to
  the vendored `site-packages`. The `.vendor/` bundle is a machine-specific install cache
  (gitignored), NOT tracked source — the tracked artifact is the build recipe + the
  `requirements-control.txt` closure it is built from.
- **FR-006 NOT-a-daemon / degrade-to-static:** the control-plane process is **optional +
  Founder-enabled** and feature-flagged **OFF** (`ws_h_control_plane`). When the process
  is absent, the surface **degrades cleanly to the ADR-0028 static read cockpit** — the
  base case, always available. The server **dispatches nothing on its own**.
- **FR-007 in-tenant (CP-6):** stdlib + FastAPI only; no external SaaS; single-file HTML
  with inline CSS/JS, no CDN. Secrets (the RBAC token map) stay in the tenant vault
  (TN-5), never in the repo.
- **Optional process unit:** a systemd (Ubuntu) / launchd (macOS) unit **example** the
  Founder opts into — not installed or enabled by default; enabling is a deliberate
  tenant act. Document that a remote device-bridge/sandbox cannot host a long-running
  process (the 2026-07-23 launch finding) — keeping the dashboard open is a
  single-command step in a real terminal, or the opt-in service unit.

## Acceptance criteria
- [ ] Offline wheel-bundle install path works with **no network**: documented recipe builds the closure; `--no-index` install (or vendored `PYTHONPATH`) boots the app (FR-008). The `.vendor/` cache stays gitignored; the tracked artifact is the recipe + closure list.
- [ ] Full dependency closure verified against real `Requires-Dist` (the `exceptiongroup` gap explicitly checked), not only pip's cross-platform resolution.
- [ ] Degrade-to-static proven: with the optional process absent / flag OFF, the ADR-0028 static read cockpit is the shipped surface; the server dispatches nothing on its own (FR-006).
- [ ] In-tenant only — no external SaaS, no CDN; RBAC token map kept out of the repo (FR-007/TN-5).
- [ ] systemd/launchd unit example provided as opt-in (not default-enabled); the sandbox/persistent-process limitation documented. `diagnostics.py` 100/100; validators green. Merged PR, green CI.

## Log
### 2026-07-24 — CEO
Created by /daslab-plan (WS-H Development, part 3). FR-008 vendored-wheels offline install
(closure verified against real Requires-Dist), FR-006 degrade-to-static + optional
Founder-enabled process, FR-007 in-tenant/no-SaaS. Distinct zone `tools/control_plane/install`
so it runs parallel to DAS-1600. Depends on the design DAS-1599.
