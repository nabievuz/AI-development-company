# ADR 0036 — Outbound interop surface + self-host Langfuse observability lens: DasLab as a governed unit others can call

- **Status:** Accepted (Backend EM authors; **CTO ratified — RACI 3.1/3.6 A — 2026-07-24**; Security Lead consulted — redaction on export, OB-3; CMO consulted — distribution, OB-4)
- **Date:** 2026-07-22 (ratified 2026-07-24)
- **Scope:** Platform / org-engine — the outbound (consumed-by-the-ecosystem) surface and a self-host observability lens
- **Deciders:** Backend EM (author), **CTO (accountable)**; Security Lead (consulted — ADR 0012 redaction on the OTLP exporter); CMO (consulted — adoption/distribution)
- **Relates:** depends on [0034](0034-agent-sdk-headless-runner.md) (headless runner) and [0024](0024-span-event-schema.md) (OTel spans); honors [0012](0012-dgox-event-store-content-classification-redaction-policy.md) (redaction), [0025](0025-events-load-bearing.md) (event store canonical), [0009](0009-harness-owns-transport-admission-layer.md) (admission); the eval/guardrail tools (promptfoo, AgentShield, Presidio) enter through the [0033](0033-ecosystem-tool-mcp-bridge.md) governed MCP edge; self-host / in-tenant boundary per [0038](0038-enterprise-internal-self-host-hardening.md) (TN-1); parity brief `docs/research/2026-07-22-daslab-vs-autonomous-coding-agents-parity.md`; MUSTAQIL master prompt v3.0 row D (`docs/research/2026-07-23-daslab-mustaqil-master-prompt-v3.md`)
- **Supersedes / Amends:** nothing — establishes the outbound surface fresh; additive; publishing is a Founder act.

> The parity analysis found DasLab's real weakness is not capability but **reach** (VS dims community 1/10, adoption 2/10), and that it lacks a live "watch it work" pane the competitors all have. This ADR fixes two outbound moves — exposing DasLab as a unit the LangChain/LangGraph ecosystem can call, and exporting the spans DasLab already emits to a **self-hosted Langfuse** lens — without weakening the governance edge or the audit system-of-record.

## Context

DasLab is a repo you clone and run; nothing in the ecosystem can *invoke* it, and there is no shared, live trace view of a wave. Both are now cheap: the ADR 0034 headless runner makes DasLab programmatically callable, and the ADR 0024 span schema already persists OpenTelemetry GenAI attribute names (`gen_ai.*`), so an OTLP exporter to a Langfuse instance is a field-mapping shim (Langfuse ingests OTLP on its own `/api/public/otel` trace endpoint — the same OTLP the ADR 0024 names were chosen for). The danger is doing either in a way that leaks governance: an external caller that reaches raw tools, or an exporter that ships unredacted content, is mistaken for the audit record, **or points off-box at a hosted SaaS observability endpoint**. The decided lens is therefore a **self-hosted, in-tenant Langfuse — explicitly NOT LangSmith and NOT any hosted/cloud observability endpoint** (master prompt v3.0 row D: "self-host Langfuse via OTLP — NOT LangSmith"; ADR 0038 TN-1 in-tenant boundary).

## Decision

**Expose DasLab's governed delivery as an ecosystem-callable unit, and add a self-hosted Langfuse instance as a non-invasive OTLP observability lens — both behind the governance edge, both in-tenant.** Binding invariants:

### OB-1 — DasLab is offered as governed delivery, not raw agents
DasLab is exposed as (i) a LangGraph node/subgraph and/or (ii) an MCP server (consumed elsewhere via `langchain-mcp-adapters`), both backed by the ADR 0034 runner. What a caller gets is *"deliver this spec through the AADL-gated org,"* not raw tool or agent access — governance rides along, so an external caller **cannot** make DasLab skip a gate, self-approve, or bypass never-auto-approve.

### OB-2 — The self-host Langfuse lens is a lens, not the system-of-record
A **self-hosted, in-tenant Langfuse instance** receives an OTLP export of the ADR 0024 spans. It is a viewing/eval surface only; `board/.events.jsonl` + the attestations stay the canonical audit record (ADR 0025). A Langfuse outage or divergence changes nothing about truth or dispatch. The exporter targets a **self-host / in-tenant endpoint only** (ADR 0038 TN-1) — it **MUST NOT default to, or silently fall back to, LangSmith or any hosted/cloud observability endpoint**. The lens is Langfuse-self-host by decision; LangSmith is explicitly out of scope.

### OB-3 — The outbound edge enforces the same admission + redaction
The outbound surface applies the ADR 0009 admission discipline and ADR 0012 content-classification/redaction at its boundary; the OTLP exporter redacts per ADR 0012 before any span leaves the process. No secret, no unredacted tool transcript crosses the boundary. The eval/guardrail tools the lens draws on (promptfoo, AgentShield, Presidio) enter DasLab **only** through the ADR 0033 governed MCP edge — least-privilege overlay allow-list, `PreToolUse` audit/deny, ADR 0012 redaction — never as a bulk import and never as a second admission path.

### OB-4 — Optional, flagged; publishing is a Founder act
The surface and the exporter are feature-flagged (ADR 0019, default OFF — `ws_d_langfuse_lens` in `config/features.yaml`). Publishing DasLab to a public registry, exposing the self-host Langfuse endpoint beyond the tenant, or pointing the exporter at any hosted project, is an explicit **Founder** decision (a distribution/governance act, QONUN-5), never automated.

## Consequences

**Positive:** DasLab becomes reachable by the LangGraph/LangChain ecosystem — a "governed-delivery subgraph" that directly attacks the adoption/community weakness — and gains a best-in-class live trace/eval pane essentially for free, since the spans are already OTel-shaped and a self-host Langfuse ingests them over OTLP unchanged. Both strengthen the "governed autonomous org" wedge rather than diluting it, and the lens keeps the whole telemetry path **in-tenant** — no telemetry leaves the box.

**Negative / accepted:** A public outbound surface is a new trust boundary to secure (mitigated by OB-1/OB-3); a self-host Langfuse adds an in-tenant service to run and operate for *viewing* (never for truth, OB-2). Running the lens self-host (rather than a hosted SaaS) shifts operational cost onto the tenant — accepted deliberately, because keeping observability in-tenant is the whole point of the MUSTAQIL enterprise-internal boundary (ADR 0038); pointing off-box at a hosted endpoint is refused except under OB-4's Founder gate and OB-3's redaction.

**Law check:** **C2** (event store canonical; the Langfuse lens is derived — OB-2). **ADR 0012** (redaction on the exporter and the outbound edge — OB-3). **ADR 0033** (eval/guardrail tools enter only through the governed MCP edge — OB-3). **LAW 8 / ADR 0009** (admission at the boundary; not re-opened). **ADR 0038 TN-1** (self-host / in-tenant only; no off-box telemetry). **AADL / never-auto-approve** (OB-1 keeps gates and Founder approval intact for external callers; OB-4 makes publishing a Founder act). **Project placement** (platform surface; exports no project content outside its project — C6).

## Enforcement / acceptance

- **Ratified by the CTO on 2026-07-24** (RACI 3.1/3.6 A); Security Lead consulted on export redaction (OB-3); CMO consulted on distribution (OB-4). Judged sound against ADR 0024 (spans are already `gen_ai.*`-named, so an OTLP exporter to a self-host Langfuse is a field-mapping shim, not a schema migration), ADR 0012 (redact-before-export, fail-closed), ADR 0025 (event store canonical; the lens is derived — C2), ADR 0033 (eval/guardrail tools ride the existing governed MCP edge, no second admission path), and ADR 0038 TN-1 (self-host / in-tenant only). The ratification **corrected the ADR's original LangSmith lean to the decided self-host-Langfuse stance** (master prompt v3.0 row D — "self-host Langfuse via OTLP, NOT LangSmith"): OB-2 now binds the exporter to an in-tenant Langfuse endpoint and forbids any hosted/cloud fallback. Status moves `Proposed` → `Accepted` on this sign-off.
- Acceptance: an external call cannot advance a ticket past an open gate (OB-1 test); the OTLP exporter emits only ADR-0012-redacted spans (OB-3 test); the exporter target resolves to an in-tenant/self-host endpoint only and a config pointing at a hosted Langfuse/LangSmith endpoint fails the check (OB-2/TN-1 test); disabling the Langfuse lens changes no board/event outcome (OB-2).
- Feature key `ws_d_langfuse_lens` in `config/features.yaml` `DEFAULTS` **OFF** (ADR 0019); publishing/exporting-off-box requires a Founder action logged to `board/.events.jsonl`.
- Any future "can something outside DasLab drive it / is the Langfuse lens the audit record / may the exporter point at a hosted endpoint?" question resolves here — governed delivery only, the lens is derived, self-host/in-tenant only, and **no**.
