# ADR 0039 — Self-hosted web control plane (extend the cockpit from read-only to governed control)

- **Status:** Proposed (Backend EM authors; **CTO ratifies — RACI 3.1/3.6**; Security Lead consulted — auth/RBAC/audit; CDO consulted — dashboard UX)
- **Date:** 2026-07-22
- **Scope:** Platform / operability — the browser-based control surface (MUSTAQIL workstream H, CONTROL)
- **Deciders:** Backend EM (author), **CTO (accountable)**; Security Lead (consulted — auth, RBAC, audit); CDO (consulted — dashboard UX)
- **Relates:** **extends** [0028](0028-cockpit-form-factor.md) (the read-only cockpit); depends on [0034](0034-agent-sdk-headless-runner.md) (headless runner to trigger runs), [0038](0038-enterprise-internal-self-host-hardening.md) (RBAC + in-tenant), [0036](0036-outbound-interop-surface-langsmith.md) (Langfuse/spans for live status); honors [0027](0027-scheduler-safety.md) (never-auto-approve + NOT-a-daemon), the event store [0024](0024-span-event-schema.md)/[0025](0025-events-load-bearing.md), redaction [0012](0012-dgox-event-store-content-classification-redaction-policy.md); program `docs/research/2026-07-22-daslab-mustaqil-master-prompt.md`
- **Supersedes / Amends:** nothing — **extends** ADR 0028; its read-only static cockpit survives as the degrade-to-static base case.

> The Founder wants DasLab installable on an Ubuntu server (Linux-first) or macOS and operable from a **browser** — submit a goal, approve a gate, trigger and watch a run. Today the cockpit (ADR 0028) is a **read-only, loopback-only, passive** view. This ADR extends it into a self-hosted, RBAC-gated **web control plane**, without breaking board-as-truth, never-auto-approve, or the NOT-a-daemon law.

## Context

ADR 0028 deliberately shipped the operator cockpit **read-only, static-first, loopback-only, NOT-a-daemon** — a passive lens, safe by construction. Enterprise-**internal** use (ADR 0038) needs more: a team operating DasLab from a browser on the tenant server, which requires (a) **networked** access, not loopback-only, and (b) **governed write** actions — submit a goal, trigger a run, approve/deny a gate. Done naively, either would break a law: a server that can sign a gate violates never-auto-approve (QONUN-5); a network-exposed control surface violates the in-tenant/secrets policy (ADR 0038 TN-1/TN-5); a persistent web daemon violates "NOT a daemon." This ADR fixes **how to add control while preserving every one of those laws**.

## Decision

**Adopt a self-hosted web control plane that EXTENDS the ADR-0028 cockpit with RBAC-gated read + governed write, run by the tenant on its own server.** Binding invariants:

### CP-1 — Extends the cockpit; one render seam, not a second cockpit
The control plane reuses the ADR-0028 `cockpit.py` `render()`/`_render_panel`/`NODATA` seam and the `cockpit_html.py` wrapper (D-4). It adds a controller layer around the *same* panels; it never forks a second view. The read cockpit remains the **degrade-to-static** base (CP-5).

### CP-2 — Networked but RBAC-gated; no anonymous access
Unlike ADR 0028's loopback-only read view, the control plane may bind to the **tenant network**, but **only** behind authentication + RBAC (ADR 0038 TN-3). Every request is identified to a role; there is no anonymous or default-open access, and it serves **only within the tenant** (ADR 0038 TN-1; egress/secrets per TN-5).

### CP-3 — Write actions are governed, audited, and never self-approving
The dashboard exposes exactly three write classes, each RBAC-authorized and written to the event store (ADR 0024/0025), redacted per ADR 0012: **(a) submit a goal** to the Founder-approved queue; **(b) trigger a run** via the WS-B headless runner (ADR 0034); **(c) approve/deny** a gate or interrupt-card. Approval is bound to a **Founder-role identity** (QONUN-5) — the dashboard, an agent, or any non-Founder role **cannot** sign a gate. A GATE-5-open deployment stays machine-blocked regardless of any button.

### CP-4 — Board stays canonical; the dashboard is a view+controller, never a source of truth
All reads and writes go **through** the board (`board/tickets/`), the goal queue, and the event store — never a parallel dashboard state (C2). A divergence resolves to the board. The control plane orchestrates existing entrypoints; it does not re-implement dispatch.

### CP-5 — NOT-a-daemon, reconciled
A web server is a long-running process, in tension with the NOT-a-daemon law. It is resolved exactly as ADR 0027/0028 resolved tempo and the live cockpit: the server is an **optional, Founder-enabled** process (a systemd/launchd unit the Founder opts into), **feature-flagged OFF** (ADR 0019), and it **degrades to the static cockpit** when absent. Crucially, the web server **dispatches nothing on its own** — a wave advances only from a human action through CP-3 or from the HEARTBEAT (ADR 0027), never because the server is running.

### CP-6 — In-tenant, self-hosted, no external SaaS
The control plane, its auth, and its data all run in-tenant (ADR 0038 TN-1). No component phones a hosted SaaS; live status is read from the in-tenant event store and self-hosted Langfuse (ADR 0036). Secrets stay in the tenant vault (TN-5).

## Consequences

**Positive:** A team can operate DasLab from a browser on their own Ubuntu server (or macOS) — submit goals, approve gates, trigger and watch runs — which is what makes enterprise-**internal** use practical beyond a single Founder at a CLI. It reuses the cockpit render, the WS-B runner, the RBAC model, and self-hosted Langfuse, so it is assembly, not new invention.

**Negative / accepted:** A networked, write-capable server is a new attack surface and a long-running process — bounded by CP-2 (auth/RBAC), CP-5 (optional, flagged, degrade-to-static, dispatches nothing itself), and CP-6 (in-tenant only). Accepted: the safeguards are the same shape DasLab already uses for the live cockpit and the tempo substrate, and the CLI + static cockpit remain the always-available fallback.

**Law check:** **C2** (board canonical; dashboard is a view+controller — CP-4). **Never-auto-approve / QONUN-5** (CP-3 — only a Founder-role identity approves a gate; the dashboard cannot self-approve). **NOT-a-daemon** (CP-5 — optional, Founder-enabled, dispatches nothing itself). **ADR 0038 TN-1/TN-3/TN-5** (in-tenant, RBAC, secrets/egress — CP-2/CP-6). **ADR 0012** (writes/status redacted). **Project placement** (platform operability code; no project content — C6).

## Enforcement / acceptance

- **Extends ADR 0028**; ratified by the **CTO**; Security Lead consulted on auth/RBAC/audit. `Proposed` until sign-off.
- A control-plane PR is reviewed against CP-1…CP-6; a PR that allows anonymous access (CP-2), lets the dashboard self-approve a gate (CP-3), keeps state outside the board (CP-4), runs an unremovable daemon that dispatches on its own (CP-5), or reaches an external SaaS (CP-6) is rejected.
- Ships behind a `config/features.yaml` flag (ADR 0019, default OFF); the static read cockpit (ADR 0028) is the degrade-to-static base and the shipped default.
- Any future "can we drive DasLab from a browser / can the dashboard approve a gate?" question resolves here — yes to the first (governed, in-tenant, RBAC), **no** to the second (Founder-only).
