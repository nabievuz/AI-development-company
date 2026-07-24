# SPEC 008 — MUSTAQIL WS-H CONTROL (self-hosted web control plane)

- **Goal:** mustaqil-ws-h-control
- **Owner:** backend-em
- **Status:** reviewed  <!-- CTO review 2026-07-24 (DAS-1598, GATE-1): every functional requirement and success criterion coherent, testable, traceable to ADR-0039 CP-1…CP-6; no unresolved clarification marker. -->

<!-- CTO GATE-1 review note (DAS-1598): the P2 write scenario is worded to the WS-E
     RBAC SSOT (config/rbac.yaml / scripts/rbac.py) this control plane MUST reuse —
     principal kinds founder/audit-team/agent/orchestrator, run.trigger Founder-only,
     audit-team read-only — NOT the on-branch spike's ad-hoc viewer<operator<founder
     tier. Binding on the Design/Development stage: bind writes to the SSOT model. -->


> WHAT/WHY only. The HOW (FastAPI controller layer, the ADR-0028 `cockpit.py`
> `render()`/`_render_panel`/`NODATA` render seam and `cockpit_html.py` wrapper, the
> RBAC token/identity mechanics, the WS-B headless-runner call, the vendored-wheel
> bundle, the systemd/launchd unit) lives in ADR-0039 and the AADL Stage-2 design
> ticket, not here. Binds to ADR-0039 (invariants CP-1…CP-6), which **extends** ADR-0028 (the
> read-only cockpit; the functional requirements and success criteria below are minted
> once each — no id is restated in this note) and depends on ADR-0034 (WS-B headless runner — trigger a run),
> ADR-0038 (RBAC + in-tenant TN-1/TN-3/TN-5), ADR-0036 (self-host Langfuse for live
> status); honors ADR-0027 (NOT-a-daemon + never-auto-approve), ADR-0024/0025 (event
> store), ADR-0012 (redaction), and Founder discovery Q6 (Founder-only approval;
> read-only audit for a small team). Sequenced **after WS-B + WS-D + WS-E**. This
> workstream is also the **WS-G PROOF** target (ADR-0037 / discovery Q1 default: the
> control-plane dashboard is the first 0→100 proof project — building it proves it).
> Folds in (hardens, does not rewrite) the on-branch spike `tools/control_plane/app.py`.

## User Scenarios

- **P1 —** Given the control-plane feature flag `ws_h_control_plane` is OFF (default), when an operator runs DasLab, then the read-only static cockpit (ADR-0028) is the shipped surface and nothing about dispatch changes — the control plane simply does not exist.
- **P1 —** Given RBAC is not configured, when any data or action endpoint is called, then it fails closed (no anonymous access) and only a data-free HTML shell and a health probe answer; there is no default-open surface.
- **P1 —** Given a Founder-role identity authenticated via RBAC, when they approve or deny a gate or interrupt-card from the browser, then the approval is honored and written to the audit trail — while a viewer or operator (any non-Founder role, an agent, or the dashboard itself) attempting the same approval is refused.
- **P1 —** Given a deployment ticket whose GATE-5 is open, when anyone presses any button in the dashboard, then the deployment stays machine-blocked — no button overrides the gate.
- **P2 —** Given a principal that the WS-E RBAC authorizes for a write action, when they submit a goal proposal or trigger a run through the WS-B runner, then the action is authorized through that RBAC — in the near-term tenant, run-trigger authority is Founder-only and the team is read-only (Q6) — executed only through the canonical board/queue/runner entrypoints, and appended to the event-store audit trail, redacted per ADR-0012; a principal not granted the action is refused with an audited deny.
- **P2 —** Given a tenant server with no internet access, when an operator installs the control plane from the vendored wheel bundle, then the app installs and boots offline (no network fetch) and answers its health probe.
- **P2 —** Given the optional control-plane process is not running, when an operator opens DasLab, then the surface degrades cleanly to the static read-only cockpit — the control plane is an opt-in convenience, never a required daemon, and it dispatches nothing on its own.

## Functional Requirements

- **FR-001** — The control plane MUST **extend** the ADR-0028 cockpit through its single render seam (`render()`/`_render_panel`/`NODATA` + the `cockpit_html.py` wrapper), adding a controller layer around the *same* panels; it MUST NOT fork a second cockpit view (ADR-0039 CP-1). The read-only cockpit remains the degrade-to-static base.
- **FR-002** — Every data and action endpoint MUST identify the request to a role via authentication + RBAC — there is no anonymous or default-open access; unconfigured RBAC MUST **fail closed** (503 for all data/action endpoints, only a health probe and a data-free HTML shell answer). The surface serves only within the tenant (ADR-0038 TN-1/TN-3) — CP-2.
- **FR-003** — The dashboard MUST expose exactly three governed write classes — (a) submit a goal proposal to the Founder-approved queue, (b) trigger a run via the WS-B headless runner (ADR-0034), (c) approve/deny a gate or interrupt-card — each RBAC-authorized and each appended to the event store (ADR-0024/0025), redacted per ADR-0012 (CP-3).
- **FR-004** — Gate/interrupt-card approval MUST bind to a **Founder-role identity** (Q6 / QONUN-5): the dashboard, an agent, or any non-Founder role MUST NOT be able to sign a gate, and a GATE-5-open deployment MUST stay machine-blocked regardless of any UI action (CP-3).
- **FR-005** — All reads and writes MUST go **through** the canonical board (`board/tickets/`), goal queue, and event store — never a parallel dashboard state; the control plane is a view+controller that orchestrates existing entrypoints and re-implements no dispatch. A divergence resolves to the board (CP-4 / C2).
- **FR-006** — The control-plane server MUST be an **optional, Founder-enabled** process, feature-flagged **OFF** by default (`ws_h_control_plane`, ADR-0019), that **degrades to the static cockpit** when absent and **dispatches nothing on its own** — a wave advances only from a human write action or the HEARTBEAT (ADR-0027), never because the server is running (CP-5 / NOT-a-daemon).
- **FR-007** — The control plane, its auth, and its data MUST all run in-tenant with **no external SaaS** dependency (ADR-0038 TN-1); live status is read from the in-tenant event store and self-hosted Langfuse (ADR-0036), and secrets stay in the tenant vault (TN-5) — CP-6.
- **FR-008** — The control plane MUST be **offline-installable** from a vendored wheel bundle (full dependency closure, platform-matched), so a no-network in-tenant server can install and boot it without reaching any package index; the vendored bundle is a machine-specific install cache, not tracked source.

## Success Criteria

- **SC-001** — A negative test proves fail-closed RBAC: unconfigured RBAC ⇒ 503 on every data/action endpoint (only the health probe and the data-free HTML shell answer); a missing/invalid token ⇒ 401; and the HTML shell leaks no board data without a token.
- **SC-002** — A negative test proves Founder-only approval: a non-Founder role (viewer/operator) that attempts to approve/deny a gate is refused with an audited deny, and a GATE-5-open deployment stays machine-blocked regardless of any dashboard action; only a Founder-role identity can approve.
- **SC-003** — An install test proves the vendored wheel bundle installs and the app boots with **no network** and answers its health probe; every governed write appends a redacted audit record (ADR-0012).
- **SC-004** — With `ws_h_control_plane` OFF (default), the read-only static cockpit is the shipped surface and dispatch behaviour is byte-identical to pre-merge; with the optional process absent, the surface degrades to the static cockpit (no error, no daemon).
- **SC-005** — `diagnostics.py` 100/100; `ruff` clean on `tools/control_plane/` (the 10 pre-existing B008 spike violations cleaned); `board_lint`/`check_spec_consistency`/`check_dependency_graph`/validators green; green CI on every WS-H PR; no `project:` field on any WS-H ticket (board_lint R9); committed wave attestation (ADR-0031/0032).
