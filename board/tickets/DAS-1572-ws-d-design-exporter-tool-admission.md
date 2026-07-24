---
id: DAS-1572
title: WS-D Design — OTLP exporter to self-host Langfuse and tool-admission model for the eval/guardrail shortlist
status: done
assignee: cto
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

### 2026-07-24 — Backend EM
**AADL Stage-2 Design (GATE-2) delivered.** Wrote the WS-D LENS design doc at
`docs/design/ws-d-langfuse-lens.md`, mirroring the WS-A/WS-B design-doc style,
each section traced to its SPEC-005 FR + ADR-0036 OB.

Design summary:
- **OTLP exporter (§1 / FR-001 / OB-2):** a field-mapping shim, not a schema
  migration — the ADR-0024 spans are already `gen_ai.*` OTel-named, so the
  exporter maps them onto an OTLP payload and POSTs to a self-host Langfuse
  `/api/public/otel`. Read-side only (reads the already-emitted span stream, never
  wired into `EventStore.append`), so it is non-invasive — no dispatch/runtime
  change. Target is resolved from `config/tenant_boundary.yaml`'s
  `langfuse_observability` endpoint (127.0.0.1:3000); no built-in hosted default,
  no fallback branch — a cloud endpoint is not a reachable configuration.
- **Redaction-on-export (§2 / FR-002 / OB-3):** every attribute is ADR-0012 M/B/F
  classified before export; Tier-B is scrubbed+capped (redact→truncate→emit,
  fail-closed) reusing the same ADR-0012 §2 scrubber as WS-A; Tier-F never crosses;
  scrubber-raise ⇒ span dropped from export, never shipped raw. No over-redaction
  of Tier-M `span_id`/`trace_id` ids.
- **Canonical event store (§3 / FR-003 / C2):** one-way canonical→lens dataflow;
  the exporter never writes back to the board/events/attestations; no dispatch
  reads the lens; Langfuse outage/divergence ⇒ stream wins, re-derive the lens.
- **Governed-tool admission (§5 / FR-005 / OB-3):** promptfoo/AgentShield/Presidio
  enter ONLY through the existing ADR-0033 edge (TB-1 sidecar, TB-2 overlay
  allow-list compiled to `board/.tool-allowlist.json`, TB-3 PreToolUse audit/deny,
  ADR-0012 redaction) — no second admission path, no bulk import, no blanket grant.
  Illustrative (NOT-applied) least-privilege starting allow-list: qa-eng→promptfoo,
  security-lead→AgentShield, redaction layer→Presidio; concrete overlay edits are
  DAS-1574's per-role security_sensitive+permission_change work.
- **In-tenant boundary (§4 / SC-004 / TN-1):** reuse the landed
  `scripts/check_in_tenant.py` + `tenant_boundary.yaml` verbatim — `observability`
  is not in `accepted_external_roles` (only `model` is), so a hosted
  Langfuse/LangSmith URL fails closed (exit 1) before any export. Off-box widening
  is a Founder act (FR-006 / OB-4).

Negative-path spec handed to DAS-1575 (§6): SC-001 flag-off byte-identical (read-
side adapter never runs); SC-002 redaction-on-export probe (planted secrets →
`[REDACTED:…]`, fail-closed, no over-redaction of ids); SC-003 tool-admission
negative (non-allow-listed promptfoo/AgentShield/Presidio refused by the same
`decide()`, audit-skip denied, every decision audited); SC-004 in-tenant target
resolution passes / hosted endpoint blocked, exporter target == checked value.

Ticket `implements: [FR-002, FR-003, FR-005]` unchanged; the doc additionally
covers FR-001/FR-004/FR-006 for completeness (traceability matrix §7).

Validators (all exit 0): `python3 scripts/board_lint.py`,
`python3 scripts/check_links.py`, `python3 scripts/check_spec_consistency.py`.

No code/config/ADRs touched — only `docs/design/ws-d-langfuse-lens.md` + this
ticket. LOCAL-ONLY (no push/PR). → `in_review`, assignee `cto` (GATE-2
accountable; Security Lead consulted on §2 redaction / §4-§5 egress+admission).

### 2026-07-24 — CTO (AADL Stage-2 / GATE-2 CLOSURE — WS-D LENS)
**GATE-2 (Design) CLOSED. Design `docs/design/ws-d-langfuse-lens.md` RATIFIED.**
Reviewed against Accepted ADR-0036 (OB-1..OB-4, self-host Langfuse NOT LangSmith —
ADR-0036 confirmed `Status: Accepted`, CTO-ratified 2026-07-24), SPEC-005
(FR-001..006 / SC-001..005), ADR-0024 (span schema), ADR-0012 (redaction),
ADR-0033 (governed tool edge), ADR-0038 TN-1. Carried the Security-Lead-consulted
review myself (accountable stage owner = CTO).

Findings:
- **§1 exporter — non-invasive read-side (OB-2/FR-001): SOUND.** Field-map shim
  over already-`gen_ai.*`-named ADR-0024 spans, not a schema migration; reads the
  emitted `board/.events.jsonl` span stream, never wired into `EventStore.append`,
  no new write path (§1.3) — SC-001 flag-OFF byte-identical holds structurally.
  Target resolved from `tenant_boundary.yaml` `langfuse_observability` only, no
  hosted default, no fallback branch.
- **§2 redaction-on-export (OB-3/FR-002): SOUND, security-consulted.** Every
  attribute ADR-0012 M/B/F classified before the boundary; reuses the SAME ADR-0012
  §2 scrubber as WS-A (no forked redactor); fail-closed redact→truncate→emit;
  Tier-F NEVER crosses; unclassifiable ⇒ `[REDACTED:unclassified]`; scrubber-raise
  ⇒ span dropped from export, never shipped raw. No Tier-M id over-redaction — the
  opaque `span_id` / derived hex `trace_id` survive (ADR-0012 high-entropy `{32,}`
  tuning note applied). Accepted.
- **§4 in-tenant enforcement (SC-004/TN-1): CONFIRMED reused verbatim.** Verified
  against the landed code: `scripts/check_in_tenant.py` reads
  `config/tenant_boundary.yaml`; the `langfuse_observability` endpoint carries
  `role: observability`, `carries_code_ip: true`, `url: http://127.0.0.1:3000`, and
  `observability` is NOT in `accepted_external_roles` (only `model` is). A hosted
  Langfuse/LangSmith URL therefore returns exit 1 and fails closed BEFORE any
  export; the exporter resolves its target from the SAME endpoint entry (§1.4), so
  the checked value == the exported-to value — no bypass. No parallel boundary
  check added.
- **§5 tool-admission (OB-3/FR-005): SOUND, security-consulted.** promptfoo /
  AgentShield / Presidio enter ONLY through the single ADR-0033 edge (TB-1 sidecar,
  TB-2 overlay allow-list → `board/.tool-allowlist.json`, TB-3 `PreToolUse`
  audit/deny, ADR-0012 redaction) — reusing the DAS-1547 (done) compiler + hook
  verbatim. No second admission path, no bulk toolkit import, no blanket grant;
  deny-all egress default (least privilege). Illustrative starting allow-list
  (qa-eng→promptfoo, security-lead→AgentShield, redaction-layer→Presidio) is
  NOT applied — no overlay written here; concrete per-role
  `security_sensitive`+`permission_change` grants deferred to DAS-1574. Correctly
  flags Presidio's own PII I/O must itself be ADR-0012-scrubbed (it complements,
  never replaces, the §2 scrubber).
- **§3 canonical event store (FR-003/C2): SOUND.** One-way canonical→lens dataflow;
  exporter never writes back; no dispatch reads the lens; outage/divergence ⇒
  stream wins, lens re-derived.
- **§6 negative-path spec: ACCEPTED for DAS-1575.** SC-001/002/003/004 each written
  as concrete assertions against the DAS-1573 exporter surface, the reused ADR-0033
  `decide()`, the ADR-0012 scrubber, and the landed `check_in_tenant.py`.
- **§7 traceability:** FR-001..006 → OB → design section → SC all mapped.

Validators (all exit 0): `python3 scripts/board_lint.py` (180 tickets, 0
violations; the DAS-1507 body-status WARN is pre-existing + unrelated),
`python3 scripts/check_links.py`, `python3 scripts/check_spec_consistency.py`
(10 SPEC.md checked, consistent).

Decision: design is a non-invasive read-side exporter, redaction-on-export is
fail-closed, tool admission rides the single ADR-0033 edge, and the target is
in-tenant-only — GATE-2 CLOSED. → `status: done`. This unblocks the two WS-D
Development tickets: DAS-1573 (OTLP exporter, zone `tools/observability`) and
DAS-1574 (eval/guardrail tool admission, zone `tools/mcp_bridges`) — distinct
zones, dispatchable in parallel; DAS-1574 also depends on the WS-A tool bridge
DAS-1547 (done). No code/config/ADRs touched — only this ticket. LOCAL-ONLY (no
push/PR/commit), accepted on local green.
