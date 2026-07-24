---
id: DAS-1572
title: WS-D Design — OTLP exporter to self-host Langfuse and tool-admission model for the eval/guardrail shortlist
status: todo
assignee: backend-em
author: ceo
dept: engineering
priority: p1
parent: DAS-1570
goal: mustaqil-ws-d-lens
spec: 005-mustaqil-ws-d-lens
implements: [FR-002, FR-003, FR-005]
labels: [security]
zone: docs/design
depends_on: [DAS-1571]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 2 — Design (closes GATE-2 for WS-D).** Design the two pieces the
Development tickets implement. No code beyond schemas/specs.

- **OTLP exporter design (OB-2/OB-3):** how the ADR-0024 span record (already
  OTel GenAI-attribute-named) maps field-for-field to an `OTLPSpanExporter`
  payload; the ADR-0012 classification/redaction pass applied before any span
  leaves the process; the self-host Langfuse ingestion endpoint shape; why
  `board/.events.jsonl` + the committed attestations stay canonical and the
  exporter can never become a second source of truth (C2).
- **Tool-admission design (FR-005):** how promptfoo, AgentShield, and Presidio
  each enter as an out-of-process MCP sidecar under the existing ADR-0033 edge
  — reusing the DAS-1547 overlay-allow-list compiler and `PreToolUse`
  audit/deny path verbatim, not a parallel mechanism. Name which role(s)
  plausibly need which tool (e.g. security-lead → AgentShield; qa-eng →
  promptfoo; the redaction/PII layer → Presidio) as an illustrative starting
  allow-list, not a live grant.
- **In-tenant target check (SC-004):** how a config check proves the exporter
  target resolves to an in-tenant/self-host endpoint only, failing closed on a
  hosted Langfuse/LangSmith URL (ADR-0038 TN-1).

Security Lead consulted (accountable stage owner = CTO; responsible =
backend-em), mirroring the WS-A GATE-2 red-team pattern — this design is
security-touching (an export boundary + a governed-tool admission model).

## Acceptance criteria
- [ ] Design doc under `docs/design/` covering the OTLP field mapping, the ADR-0012 redaction pass, the self-host-only target check, and the tool-admission reuse of the ADR-0033 edge for promptfoo/AgentShield/Presidio — each traced to its FR.
- [ ] Negative-path behaviour specified for SC-002/SC-003/SC-004 (redaction probe, non-allow-listed tool refusal, hosted-endpoint rejection) so DAS-1575 can test it.
- [ ] Security Lead review recorded. `board_lint`/`check_spec_consistency` green.

## Log
### 2026-07-24 — Senior Product Manager
Created by /daslab-plan (WS-D Design). Exporter field-mapping + redaction design;
tool-admission design reusing the ADR-0033 edge for the eval/guardrail shortlist.
