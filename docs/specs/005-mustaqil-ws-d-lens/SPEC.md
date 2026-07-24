# SPEC 005 — MUSTAQIL WS-D LENS (self-host observability + governed-tool admission)

- **Goal:** mustaqil-ws-d-lens
- **Owner:** backend-em
- **Status:** reviewed

> WHAT/WHY only. The HOW (the OTLP exporter shape, the self-host Langfuse
> deployment, the promptfoo/AgentShield/Presidio wiring) lives in ADR-0036 and
> the AADL Stage-2 design ticket, not here. Binds to ADR-0036 (OB-1…OB-4),
> ADR-0024 (span-event schema, already `gen_ai.*`-named), ADR-0012 (redaction),
> ADR-0033 (the governed MCP edge that admits promptfoo/AgentShield/Presidio),
> the master prompt (`docs/research/2026-07-23-daslab-mustaqil-master-prompt-v3.md`,
> row D + Part 2), and Founder discovery answers Q5/Q9/Q11.

## User Scenarios

- **P1 —** Given the ADR-0024 spans DasLab already emits, when the WS-D exporter runs, then it ships an OTLP export of those spans to a **self-hosted** Langfuse instance — never to a hosted LangSmith/Langfuse-cloud endpoint — so trace/eval viewing works without any code or IP leaving the tenant.
- **P1 —** Given the exporter is about to ship a span off-process, when it builds the OTLP payload, then every field is classified and redacted under ADR-0012 first, so no secret or unredacted tool transcript ever reaches the observability lens.
- **P1 —** Given the self-host Langfuse lens receives an export (or is unreachable, or diverges from the event store), when anyone asks "what actually happened," then `board/.events.jsonl` + the committed attestations remain the answer — Langfuse is a view, never the audit record.
- **P1 —** Given the WS-D feature flag (`ws_d_langfuse_lens`) is OFF (default), when a wave runs, then no span is exported and dispatch behaves exactly as today — the exporter simply does not run.
- **P2 —** Given a role whose overlay allow-lists an eval/guardrail tool (promptfoo, AgentShield, or Presidio), when that role invokes it, then the call enters only through the ADR-0033 governed MCP edge — least-privilege allow-list, `PreToolUse` audit/deny, ADR-0012 redaction — identically to any other external tool; a role that does NOT allow-list the tool is refused.
- **P2 —** Given WS-D and WS-A run in parallel (D does not wait on A's full closure, only on the 0033 edge existing), when WS-D admits promptfoo/AgentShield/Presidio, then it reuses the existing 0033 admission chain unmodified — WS-D adds no second tool-entry path.

## Functional Requirements

- **FR-001** — DasLab MUST export the ADR-0024 OTel-shaped spans via an OTLP exporter to a **self-hosted** Langfuse instance (in-tenant, ADR-0038 TN-1); the exporter MUST NOT default to, or silently fall back to, any hosted/external observability endpoint (OB-2, master prompt row D — "NOT LangSmith").
- **FR-002** — The OTLP exporter MUST apply ADR-0012 content-classification + redaction to every span/attribute before it leaves the process; no secret or unredacted tool transcript may cross the export boundary (OB-3).
- **FR-003** — `board/.events.jsonl` and the committed wave attestations (ADR-0025/0031/0032) remain the canonical audit record; the self-host Langfuse lens is a derived view only — disabling or losing it MUST change no board/dispatch outcome (OB-2, C2).
- **FR-004** — The WS-D exporter MUST be feature-flagged in `config/features.yaml` DEFAULT **OFF** (`ws_d_langfuse_lens`, ADR-0019); with the flag OFF, dispatch and event emission are byte-identical to pre-merge; rollback is disabling the flag / removing the exporter wiring.
- **FR-005** — Each of the eval/guardrail tools admitted under WS-D (promptfoo, AgentShield, Presidio) MUST enter DasLab only through the existing ADR-0033 governed MCP edge (out-of-process sidecar, least-privilege overlay allow-list, `PreToolUse` audit/deny, ADR-0012 redaction) — never as a bulk toolkit import, never as a second admission path, and never with a global/blanket grant.
- **FR-006** — Publishing the self-host Langfuse endpoint beyond the tenant, or pointing the exporter at any hosted project, MUST be an explicit Founder act (OB-4, QONUN-5) — never automated or self-triggered by a workstream ticket.

## Success Criteria

- **SC-001** — With the flag OFF (default), no OTLP export occurs and a wave's dispatch/event behaviour is byte-identical to pre-merge; flipping the flag ON begins export without altering any board/dispatch outcome.
- **SC-002** — A redaction probe proves every exported span/attribute is ADR-0012 classified + redacted before leaving the process (no secret/PII/tool-transcript substring survives in the exported payload).
- **SC-003** — A negative test proves a role NOT allow-listing promptfoo/AgentShield/Presidio is refused the tool, and a call that skips the `PreToolUse` audit on any of the three is denied — identical guarantees to the base 0033 edge, with no WS-D-specific bypass.
- **SC-004** — A check proves the exporter target resolves to an in-tenant/self-hosted endpoint only (TN-1); a config pointing at a hosted Langfuse/LangSmith endpoint fails this check.
- **SC-005** — `diagnostics.py` 100/100; `board_lint` / `check_spec_consistency` / `check_dependency_graph` all green; no `project:` field on any WS-D ticket (board_lint R9); committed wave attestation for every merged WS-D PR.
