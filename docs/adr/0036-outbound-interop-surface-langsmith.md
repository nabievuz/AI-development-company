# ADR 0036 — Outbound interop surface + LangSmith observability: DasLab as a governed unit others can call

- **Status:** Proposed (Backend EM authors; **CTO ratifies — RACI 3.1/3.6**; Security Lead consulted — redaction on export; CMO consulted — distribution)
- **Date:** 2026-07-22
- **Scope:** Platform / org-engine — the outbound (consumed-by-the-ecosystem) surface and an observability lens
- **Deciders:** Backend EM (author), **CTO (accountable)**; Security Lead (consulted — ADR 0012 redaction on the OTLP exporter); CMO (consulted — adoption/distribution)
- **Relates:** depends on [0034](0034-agent-sdk-headless-runner.md) (headless runner) and [0024](0024-span-event-schema.md) (OTel spans); honors [0012](0012-dgox-event-store-content-classification-redaction-policy.md) (redaction), [0025](0025-events-load-bearing.md) (event store canonical), [0009](0009-harness-owns-transport-admission-layer.md) (admission); parity brief `docs/research/2026-07-22-daslab-vs-autonomous-coding-agents-parity.md`
- **Supersedes / Amends:** nothing — establishes the outbound surface fresh; additive; publishing is a Founder act.

> The parity analysis found DasLab's real weakness is not capability but **reach** (VS dims community 1/10, adoption 2/10), and that it lacks a live "watch it work" pane the competitors all have. This ADR fixes two outbound moves — exposing DasLab as a unit the LangChain/LangGraph ecosystem can call, and exporting the spans DasLab already emits to LangSmith — without weakening the governance edge or the audit system-of-record.

## Context

DasLab is a repo you clone and run; nothing in the ecosystem can *invoke* it, and there is no shared, live trace view of a wave. Both are now cheap: the ADR 0034 headless runner makes DasLab programmatically callable, and the ADR 0024 span schema already persists OpenTelemetry GenAI attribute names (`gen_ai.*`), so a LangSmith exporter is a field-mapping shim (LangSmith ingests OTLP at `https://api.smith.langchain.com/otel`). The danger is doing either in a way that leaks governance: an external caller that reaches raw tools, or an exporter that ships unredacted content or is mistaken for the audit record.

## Decision

**Expose DasLab's governed delivery as an ecosystem-callable unit, and add LangSmith as a non-invasive OTLP observability lens — both behind the governance edge.** Binding invariants:

### OB-1 — DasLab is offered as governed delivery, not raw agents
DasLab is exposed as (i) a LangGraph node/subgraph and/or (ii) an MCP server (consumed elsewhere via `langchain-mcp-adapters`), both backed by the ADR 0034 runner. What a caller gets is *"deliver this spec through the AADL-gated org,"* not raw tool or agent access — governance rides along, so an external caller **cannot** make DasLab skip a gate, self-approve, or bypass never-auto-approve.

### OB-2 — LangSmith is a lens, not the system-of-record
LangSmith receives an OTLP export of the ADR 0024 spans. It is a viewing/eval surface only; `board/.events.jsonl` + the attestations stay the canonical audit record (ADR 0025). A LangSmith outage or divergence changes nothing about truth or dispatch.

### OB-3 — The outbound edge enforces the same admission + redaction
The outbound surface applies the ADR 0009 admission discipline and ADR 0012 content-classification/redaction at its boundary; the OTLP exporter redacts per ADR 0012 before any span leaves the process. No secret, no unredacted tool transcript crosses the boundary.

### OB-4 — Optional, flagged; publishing is a Founder act
The surface and the exporter are feature-flagged (ADR 0019, default OFF). Publishing DasLab to a public registry, or pointing the exporter at a hosted LangSmith project, is an explicit **Founder** decision (a distribution/governance act, QONUN-5), never automated.

## Consequences

**Positive:** DasLab becomes reachable by the LangGraph/LangChain ecosystem — a "governed-delivery subgraph" that directly attacks the adoption/community weakness — and gains a best-in-class live trace/eval pane essentially for free, since the spans are already OTel-shaped. Both strengthen the "governed autonomous org" wedge rather than diluting it.

**Negative / accepted:** A public outbound surface is a new trust boundary to secure (mitigated by OB-1/OB-3); LangSmith adds an external dependency for *viewing* (never for truth, OB-2). A hosted exporter sends redacted telemetry off-box — accepted only under OB-4's Founder gate and OB-3's redaction.

**Law check:** **C2** (event store canonical; LangSmith is derived — OB-2). **ADR 0012** (redaction on the exporter and the outbound edge — OB-3). **LAW 8 / ADR 0009** (admission at the boundary; not re-opened). **AADL / never-auto-approve** (OB-1 keeps gates and Founder approval intact for external callers; OB-4 makes publishing a Founder act). **Project placement** (platform surface; exports no project content outside its project — C6).

## Enforcement / acceptance

- Ratified by the **CTO**; Security Lead consulted on export redaction; CMO consulted on distribution. `Proposed` until sign-off.
- Acceptance: an external call cannot advance a ticket past an open gate (OB-1 test); the OTLP exporter emits only ADR-0012-redacted spans (OB-3 test); disabling LangSmith changes no board/event outcome (OB-2).
- Feature keys in `config/features.yaml` `DEFAULTS` **OFF** (ADR 0019); publishing/exporting requires a Founder action logged to `board/.events.jsonl`.
- Any future "can something outside DasLab drive it / is LangSmith the audit record?" question resolves here — governed delivery only, and **no**.
