---
id: DAS-1453
title: Author ADR-0024 span-event schema (OTel GenAI semantic-convention names)
status: done
assignee: chairman
author: ceo
dept: engineering
priority: p1
parent: DAS-1441
goal: organism-ws3-bridge
depends_on: [DAS-1442]
zone: docs/adr
created: 2026-07-03
updated: 2026-07-03
---

## Description

**What.** Author a new Architecture Decision Record, `docs/adr/0024-span-event-schema.md`,
that decides the on-disk **span record** shape for DasLab's observability layer: a
distributed-trace-style span that captures one unit of agent work (an invoke, a chat
turn, a tool call, a wave, or a whole run). This ADR is spec-of-record for the code
ticket DAS-1454, which will implement the span builder/validator in `scripts/dgox/`.

**Why.** DasLab already has an append-only JSONL event store (`scripts/dgox/events.py`,
ADR 0011) with two load-bearing shapes (`routing_decision`, `agent_invocation`) and a
list of reserved future event types (`run_start`, `run_end`, `tool_call`, …). What is
missing is a **span** abstraction that ties those discrete events into a trace tree with
timing and token-cost accounting, so a run can be reconstructed as a parent/child span
hierarchy and — critically — so that a real OpenTelemetry exporter becomes a trivial
future adapter. The decision here is to adopt **OTel GenAI semantic-convention attribute
NAMES** (`gen_ai.agent.name`, `gen_ai.usage.input_tokens`, …) as our field names now,
even though we are not wiring an OTel SDK yet. Adopting the vendor-neutral names up front
is the hard-to-reverse decision an ADR exists to record: it makes a future `OTLPSpanExporter`
a field-mapping shim rather than a schema migration.

**Embedded context — how spans relate to what exists.**
- **Event store (`scripts/dgox/events.py`).** Append-only JSONL, one JSON object per
  line, written via `EventStore.append`. Common envelope = `event_type`, `ticket_id`,
  `created_at` (caller-supplied — NEVER generated inside a pure helper; a convenience
  `utcnow()` wrapper exists for production callers), optional `run_id`. Builder helpers
  are pure and take `created_at` as an argument so they stay deterministic/testable.
  `_VALID_EVENT_TYPES` already reserves `run_start`, `run_end`, `tool_call`, etc. The
  span schema in this ADR is a NEW shape that layers ON this same append-only, pure-builder,
  caller-supplied-timestamp discipline — it does not replace the event store.
- **graph_state mirror (`scripts/dgox/state.py`).** The `artifacts` field group already
  contains a `trace_ids: list[str]` field (sole writer: worker/CI), documented as "link
  artifact fields to events." That is a **mirror/pointer field**, NOT the span records
  themselves. This ADR must explicitly reconcile with it: `graph_state.trace_ids` holds
  the trace/span identifiers that POINT AT span records; the span records live in the
  (span) event stream. The ADR states which side is canonical (the span stream is the
  record; `trace_ids` is a derived mirror, consistent with graph_state being a derived,
  never-primary mirror per ADR 0011 §1).
- **ADR index (`docs/adr/README.md`).** ADRs are append-only, next free number is
  **0024** (0001–0022 exist; new ADRs take the next free number). The table columns are
  `# | Decision | Status | Date`, and there is a "Themes" section grouping ADRs by range.

**Extend-vs-new posture.** This is a **NEW ADR file** (`0024-span-event-schema.md`) —
ADRs are append-only and never edited in place, so a new decision always takes a new
number. The ADR **specifies a schema** (a decision record + field contract); it does NOT
write any Python — implementation is DAS-1454. Within the doc, the span shape is
positioned as an **extension of the existing event-store contract** (same envelope
discipline, same append-only rule, same caller-supplied `created_at`), not a competing
store. The only existing file this ticket EDITS is `docs/adr/README.md` (add the index
row + a Themes mention). It does not modify `events.py` or `state.py` — it only
references and reconciles with them.

**Key existing files this touches.**
- `docs/adr/0024-span-event-schema.md` — NEW (the ADR authored here).
- `docs/adr/README.md` — EDIT (add index row + theme note).
- `scripts/dgox/events.py` — REFERENCE only (envelope discipline, reserved event types,
  pure caller-supplied-`created_at` builder pattern the span shape must follow).
- `scripts/dgox/state.py` — REFERENCE only (`FIELD_GROUPS["artifacts"]` includes
  `trace_ids`; reconcile the span records vs. the mirror field).

**AADL stage: GATE-1 Planning.** This is a planning/design authoring ticket that produces
the decision record consumed downstream; it does not ship code.

### Span record — decision content to specify in the ADR

The ADR must define a single span record with at least these fields (state the JSON
field name, then the OTel GenAI attribute name it maps to):

- **`trace_id`** — the ticket id (e.g. `DAS-1453`); all spans for a ticket's work share
  one trace. (Maps to OTel `trace_id`; ADR notes our id is human-readable, not the OTel
  16-byte hex, and that the future exporter derives/hashes as needed.)
- **`span_id`** — unique id for this span.
- **`parent_span_id`** — the enclosing span (null for a root `run`/`wave` span), giving
  the trace tree.
- **`kind`** — one of `{invoke_agent, chat, execute_tool, wave, run}`. (Names align with
  the OTel GenAI operation names, e.g. `invoke_agent`, `execute_tool`, `chat`.)
- **agent identity** — `gen_ai.agent.name` (agent/role name) and the agent **tier/model**
  (e.g. `gen_ai.request.model` or a tier attribute — the ADR fixes the exact name).
- **timing** — `start` and `end` timestamps (caller-supplied ISO-8601 `Z`, same rule as
  the event store) and a derived `duration` (ms).
- **token accounting** — input/output token counts via `gen_ai.usage.input_tokens` and
  `gen_ai.usage.output_tokens`, plus a **`cached`** indicator (cache-read tokens / cached
  flag).
- **`status`** — span outcome (e.g. `ok` / `error`, aligned with OTel span status).
- **`created_at`** — caller-supplied (append-only discipline; never generated inside a
  pure builder).

Additional required decisions in the ADR:
- **Append-only** — spans are never rewritten; a correction is a new compensating span
  (same rule as ADR 0011's event store).
- **OTel GenAI semantic-convention NAMES** — the attribute names above are the actual
  field names (or an explicitly documented mapping table), so a real OTel exporter is a
  trivial future adapter and not a schema change.
- **Reconciliation with `graph_state.trace_ids`** — explain that `trace_ids` is a mirror
  of pointers into the span stream, that the span stream is the record of truth for span
  data, and that the mirror stays consistent with the "board/event stream is canonical,
  graph_state is derived" rule (ADR 0011 §1).
- **Index + theme** — add the `| 0024 | … | Proposed | 2026-07-03 |` row to
  `docs/adr/README.md` and a Themes-section note (an observability/tracing theme, or an
  extension of the DGO-X control-plane theme).

## Acceptance criteria

- [ ] `docs/adr/0024-span-event-schema.md` is authored and merged, following the standard
      ADR structure (Context / Decision / Consequences).
- [ ] The span record defines **`trace_id` (= ticket id)**, **`span_id`**, and
      **`parent_span_id`** (trace-tree parent), with `parent_span_id` null for root spans.
- [ ] The **`kind`** enum is defined as exactly `{invoke_agent, chat, execute_tool, wave, run}`.
- [ ] The record includes agent **name** + **tier/model**, **start/end** timestamps + a
      derived **duration**, **input/output token counts**, a **`cached`** indicator, and
      a **`status`** field.
- [ ] **OTel GenAI semantic-convention attribute NAMES** are specified for the fields
      (at minimum `gen_ai.agent.name`, `gen_ai.usage.input_tokens`,
      `gen_ai.usage.output_tokens`), stated so a real OTel exporter is a trivial adapter.
- [ ] The ADR states the record is **append-only** and that **`created_at` is
      caller-supplied** (never generated inside a pure builder — consistent with
      `scripts/dgox/events.py`).
- [ ] The ADR explicitly **reconciles with the existing `graph_state.trace_ids` mirror
      field** (`scripts/dgox/state.py`, `FIELD_GROUPS["artifacts"]`): span records are the
      record of truth; `trace_ids` is a derived mirror of pointers, board/stream canonical.
- [ ] `docs/adr/README.md` has a new **index row** for ADR 0024 (`# | Decision | Status |
      Date` columns) and a **Themes-section** mention.
- [ ] The ADR takes the **next free number (0024)** and does not edit any prior ADR in place.

**Produces:** `adr-0024` (consumed by DAS-1454, the span builder/validator implementation).

## Log

### 2026-07-03 — CEO
Created from ORGANISM program-plan decomposition (/daslab-plan). Spec-of-record: docs/research/ORGANISM-PROGRAM-PLAN.md.

### 2026-07-03 — CTO
Authored `docs/adr/0024-span-event-schema.md` (Proposed, GATE-1 Planning) and added the
index row + an Observability/tracing Themes note to `docs/adr/README.md`. The ADR decides:
- A new append-only `span` event on the ADR 0011 event store (same envelope, pure builders,
  caller-supplied `created_at`/`start`/`end`; never rewritten — a correction is a compensating span).
- Span fields: `trace_id` = ticket id, `span_id`, `parent_span_id` (null ⇒ root), `kind` ∈
  {invoke_agent, chat, execute_tool, wave, run}, agent name + model/tier (one field — dispatch
  axis), `start`/`end` + derived `duration_ms`, input/output tokens, a `cached` flag +
  `cached_input_tokens`, and `status` ∈ {ok, error}.
- Field names ARE the OTel GenAI semantic-convention attribute names (`gen_ai.agent.name`,
  `gen_ai.usage.input_tokens`/`output_tokens`/`cached_input_tokens`, `gen_ai.request.model`,
  `kind`→`gen_ai.operation.name`) with one authoritative mapping table, so a real OTLPSpanExporter
  is a field-mapping shim, not a schema migration. DasLab-only concepts namespaced `daslab.*`.
- Reconciles `graph_state.trace_ids` (`state.py` `FIELD_GROUPS["artifacts"]`) as a DERIVED mirror
  of POINTERS into the canonical span stream (ADR 0011 §1 canonical/derived split); stream wins.
- Implementation deferred to DAS-1454 (register `span` in `_VALID_EVENT_TYPES`, build/validate).
Validators: `python3 scripts/diagnostics.py` → 100/100; `python3 scripts/board_lint.py` → 0.
Files: docs/adr/0024-span-event-schema.md (new), docs/adr/README.md (index row + theme).
Set status → in_review; assignee → chairman for the GATE-1 Planning ADR review (next wave).
Committed locally on `feat/das-1453-adr-0024-span-schema` (LOCAL-ONLY per ORGANISM build; no push/PR).

### 2026-07-03 — Chairman of the Board
GATE-1 (Planning) sign-off — **PASS / Accepted**. Reviewed `docs/adr/0024-span-event-schema.md`
in full against the ticket's Acceptance criteria and the AADL GATE-1 Planning gate
(`governance/policies/ai-agent-lifecycle.md` §3). Did not review my own work — the ADR was
authored by CTO (author: ceo, per ROUTING this review lands on the Chairman for a governance/policy
ADR sign-off).

Verified (all 9 acceptance criteria met):
- Standard ADR structure (Context / Decision / Consequences); next free number 0024; no prior ADR edited in place.
- Span fields: `trace_id` = ticket id, `span_id`, `parent_span_id` (`null` ⇒ root) — trace tree correct (§1).
- `kind` enum is exactly `{invoke_agent, chat, execute_tool, wave, run}` (§1, §2 mapping row).
- Record carries agent name (`gen_ai.agent.name`) + model/tier (`gen_ai.request.model`, one dispatch axis),
  `start`/`end` + derived `duration_ms`, in/out tokens, `cached` + `cached_input_tokens`, and `status` ∈ {ok, error} (§1).
- OTel GenAI semantic-convention NAMES are the field names with one authoritative mapping table (§2); DasLab-only
  concepts namespaced `daslab.*`; a real `OTLPSpanExporter` is a field-mapping shim, not a schema migration.
- Append-only + caller-supplied `created_at`/`start`/`end` (never `utcnow()` in a pure builder), consistent with
  `scripts/dgox/events.py` (§3).
- Reconciles `graph_state.trace_ids` (`state.py` `FIELD_GROUPS["artifacts"]`) as a DERIVED mirror of pointers into
  the canonical span stream; stream wins on divergence (ADR 0011 §1 canonical/derived split) (§4).
- `docs/adr/README.md` has the 0024 index row + an Observability/tracing Themes note (ORGANISM WS3 BRIDGE);
  all internal links resolve (0011, 0023, `../research/ORGANISM-PROGRAM-PLAN.md`).
- Implementation correctly deferred to DAS-1454 (register `span` in `_VALID_EVENT_TYPES`, `build_span`/`validate_span`);
  no code shipped here. Consistent posture with sibling ADR-0023 (extend-not-fork the ADR 0011 event store).

GATE-1 items: for a **platform/org-engine ADR** (not a project agent-program), the applicable Planning-gate items —
explicit scope boundaries and a rationale-with-law-check recorded in a merged decision record — are satisfied. The
project-lifecycle GATE-1 items (finance-analyst token/infra budget, legal-analyst risk-ethics sign-off, business KPI,
data feasibility) are N/A to a schema-decision ADR and apply when a shipping agent program enters its own Planning stage.

ADR status `Proposed` → `Accepted` (and the matching README index-row status). Ticket → `done`.
Note: local-only "done" here = green validators + completed review (no PR/merge, per the ORGANISM LOCAL-ONLY build directive).
Validators re-run at review: `python3 scripts/diagnostics.py` → 100/100; `python3 scripts/board_lint.py` → 0 violations.
Committing locally on `feat/das-1453-adr-0024-span-schema` (no push).
