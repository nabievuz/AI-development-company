# ADR 0038 — Enterprise-internal self-host hardening (the TENANT target)

- **Status:** Proposed (Backend EM authors; **CTO ratifies — RACI 3.1/3.6**; Security Lead + COO consulted — RBAC, audit, secrets)
- **Date:** 2026-07-22
- **Scope:** Platform / org-engine — the enterprise-**internal** self-hosted deployment target (MUSTAQIL workstream E, TENANT)
- **Deciders:** Backend EM (author), **CTO (accountable)**; Security Lead (consulted — RBAC, secrets, audit export); COO (consulted — GATE-6 maintenance surface)
- **Relates:** MUSTAQIL WS-E; depends on [0036](0036-outbound-interop-surface-langsmith.md) (self-host observability), [0033](0033-ecosystem-tool-mcp-bridge.md) (browser egress), the redaction policy [0012](0012-dgox-event-store-content-classification-redaction-policy.md), the audit substrate [0024](0024-span-event-schema.md)/[0025](0025-events-load-bearing.md)/[0031](0031-wave-runner-attestation.md), portability [0003](0003-self-locating-root.md); the web control plane [0039](0039-self-hosted-web-control-plane.md); program `docs/research/2026-07-22-daslab-mustaqil-master-prompt.md`
- **Supersedes / Amends:** nothing — establishes the internal-self-host target fresh; explicitly does **not** commit to enterprise-SaaS packaging.

> The Founder chose the enterprise model that fits DasLab's identity: a company runs DasLab **on its own infrastructure** to build its own software, with code and IP staying in-tenant. That is a self-host hardening target, **not** a sellable SaaS shell. This ADR fixes what "enterprise-internal" requires and, just as importantly, what it deliberately excludes.

## Context

DasLab's governance is already enterprise-grade (AADL, RACI, attestation, redaction, never-auto-approve — aligned to NIST AI RMF / ISO 42001 / OWASP-LLM per `ai-agent-lifecycle.md`). Its *packaging* is not: the audits record single-user and macOS-path assumptions, there is no role-based access control mapping, and observability was pointed at a hosted SaaS (LangSmith) in the first interop draft. For the code/IP-privacy use case enterprises actually prefer — self-hosted, nothing leaves the tenant — the missing pieces are portability, RBAC, audit export, and an in-tenant stack. The trap is scope creep into SOC 2 certification, SSO/SCIM, and multi-tenant billing — a different, funded, product-company effort.

## Decision

**Adopt enterprise-internal self-host as the TENANT target with invariants; explicitly exclude SaaS packaging.** Invariants:

### TN-1 — In-tenant only; nothing leaves the boundary
The sandbox (E2B / OpenHands, MUSTAQIL WS-C), observability (**self-hosted Langfuse**, ADR 0036 — not hosted LangSmith), and the tool bridges (ADR 0033) all run inside the tenant. No external SaaS dependency is required to operate; any egress is redacted per ADR 0012, and no source code or IP leaves the tenant.

### TN-2 — Remove single-user / macOS assumptions
All paths are self-locating (ADR 0003, `check_no_hardcoded_paths`); the engine runs Linux-first in CI and in the tenant; per-user configuration and workspace isolation replace the single-operator assumption. This closes the named audit weakness rather than documenting around it. The engine **installs on an Ubuntu server (Linux-first) or macOS**, and is operated both from the CLI and from the **self-hosted web control plane** (ADR 0039).

### TN-3 — RBAC mapped to the org + Founder gate
The 32-role org and the Founder gate map onto real access control: who may approve which AADL gate, trigger a run (`/daslab-run`, the headless runner ADR 0034), and read the audit trail — least privilege by default. Every never-auto-approve category (QONUN-5) maps to a human-only role; an agent identity can never hold gate-approval authority.

### TN-4 — Audit export to the tenant's SIEM
The event store + attestation (ADR 0024/0025/0031/0032) are exportable read-only to the tenant's SIEM as OTel/JSON, redacted per ADR 0012. The tenant's own security team can audit every routing/tool/gate/approval/run event without DasLab holding the data.

### TN-5 — Secrets and egress policy
Secrets live in the tenant's vault, never in the repo or in spans (gitleaks + ADR 0012); the browser/computer-use tool (ADR 0033 TB-4) is treated as untrusted egress and constrained by an egress allow-list at the tenant boundary.

### Scope boundary (binding)
This is **internal self-host**. SOC 2 certification, SSO/SAML/SCIM, multi-tenant isolation, and billing are **out of scope** — a separate, later, Founder-funded program. Delivering TN-1…TN-5 does not imply or start that work.

## Consequences

**Positive:** Positions DasLab for the enterprise model that matches its OSS-and-governance identity — code/IP privacy via self-host, no vendor lock-in — and turns existing governance (audit, attestation, redaction) into a real enterprise-internal audit story. The hardening is bounded and mostly closes known weaknesses (portability, single-user) rather than building new product surface.

**Negative / accepted:** RBAC, multi-user isolation, and SIEM export are real engineering, and self-hosting the sandbox + Langfuse adds operational surface the tenant must run. Accepted — it is the deliberately-scoped floor for internal enterprise use, and far smaller than a SaaS shell. Excluding SOC 2/SSO means DasLab is not yet *sellable* to enterprises, only *runnable inside* one — which is exactly the chosen path.

**Law check:** **Project placement** (platform hardening; no project content leaks — C6). **Portability / ADR 0003** (TN-2). **Redaction / ADR 0012** (TN-1/TN-4/TN-5). **Never-auto-approve / QONUN-5** (TN-3 RBAC reinforces it). **Model allocation** unchanged. **Board audit** (TN-4 strengthens the existing trail).

## Enforcement / acceptance

- Ratified by the **CTO**; Security Lead + COO consulted. `Proposed` until sign-off.
- TN-1…TN-5 are the **Definition-of-Done for MUSTAQIL WS-E (TENANT)**; a WS-E PR is reviewed against them, and TN-2 portability is gated by `check_no_hardcoded_paths`.
- The scope boundary is binding: a PR that adds SOC 2 tooling, SSO, or multi-tenant billing under this ADR is out of scope and rejected — that work needs its own funded program and ADR.
- Any future "what does enterprise-internal require / are we building a SaaS?" question resolves here — internal self-host, and **no**.
