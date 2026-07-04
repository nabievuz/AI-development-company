# ADR 0024 — Span-event schema (OTel GenAI semantic-convention attribute names)

**Status:** Accepted
**Date:** 2026-07-03

## Context

Program **ORGANISM** WS3 "BRIDGE" (the observability / telemetry seam) needs a
first-class, on-disk **span** — a distributed-trace-style record that captures one
unit of agent work (an agent invocation, a chat turn, a tool call, a wave, or a
whole run) with timing and token-cost accounting — so a run can be reconstructed
as a parent/child span tree and, critically, so that a real OpenTelemetry
exporter becomes a trivial future adapter rather than a schema migration.

Today the engine has the append-only event store but not the span abstraction
that ties its discrete events into a timed trace tree:

- An append-only JSONL **event store** (`board/.events.jsonl`,
  [ADR 0011](0011-dgox-phase-1-data-contracts.md)) with a common envelope
  (`event_type`, `ticket_id`, `created_at`, optional `run_id`) and two
  load-bearing shapes, `routing_decision` and `agent_invocation`, written through
  `EventStore.append`. Its builder helpers are **pure** and take `created_at` as
  an argument (never `utcnow()` inside a helper) so they stay deterministic and
  testable; `_VALID_EVENT_TYPES` reserves future types (`tool_call`, `run_start`,
  `run_end`, …) but does **not** yet include `span` (`scripts/dgox/events.py`).
- A derived **graph_state mirror** (`scripts/dgox/state.py`) whose
  `FIELD_GROUPS["artifacts"]` group already contains a
  `trace_ids: list[str]` field (sole writer: worker/CI), documented as "link
  artifact fields to events." That field is a **mirror of pointers**, not the span
  records themselves — graph_state is a derived, never-primary mirror (ADR 0011
  §1; the board/stream is canonical, graph_state loses on any divergence).

What is missing is the **span record** itself: a shape that layers on the
existing append-only, pure-builder, caller-supplied-timestamp discipline and
carries the trace tree, agent identity, timing, and token/cache accounting.

This ADR **decides** that shape. It is a **GATE-1 Planning** deliverable — an ADR
only; **no code ships here**. Implementation (the span builder + validator in
`scripts/dgox/`, registering `span` in `_VALID_EVENT_TYPES`) lands in the consumer
ticket **DAS-1454**. The only file this ticket edits besides authoring the ADR is
`docs/adr/README.md` (index row + theme note). Spec-of-record:
[`docs/research/ORGANISM-PROGRAM-PLAN.md`](../research/ORGANISM-PROGRAM-PLAN.md)
(WS3 BRIDGE; §9 approved defaults — Founder-approved 2026-07-03).

**Posture: EXTEND, do not fork.** The span record is a **new event shape on the
existing store**, not a competing store. Same envelope, same append-only rule,
same caller-supplied `created_at`, same pure-builder discipline. It introduces
**no second source of truth**: `board/.events.jsonl` remains canonical for
history (ADR 0011), board ticket files remain canonical for ticket state
(ADR 0010 C2), and `graph_state.trace_ids` remains a derived mirror.

**Why the vendor-neutral names now.** Adopting the OpenTelemetry **GenAI
semantic-convention attribute names** (`gen_ai.agent.name`,
`gen_ai.usage.input_tokens`, …) as our field names — *before* we wire any OTel
SDK — is the hard-to-reverse decision an ADR exists to record. It makes a future
`OTLPSpanExporter` a **field-mapping shim** over already-correctly-named data,
not a rename-everything migration. Renaming a persisted, append-only field later
is exactly the cost we are paying an ADR to avoid.

## Decision

### 1. The span record

A span is a JSON object appended to the event store as a new event type,
`event_type: "span"`. It carries the ADR 0011 common **envelope** unchanged
(`event_type`, `ticket_id`, `created_at`, optional `run_id`) plus the span
payload. Fields (JSON field name → the OTel attribute name it maps to; see the
mapping table in §2):

- **`trace_id`** — **the ticket id** (e.g. `"DAS-1453"`). Every span emitted for a
  ticket's work shares one trace. (→ OTel `trace_id`. Our id is a human-readable
  string, not the OTel 16-byte hex; the future exporter derives/hashes a
  conformant id — a pure function of the ticket id — at export time.)
- **`span_id`** — a unique id for this span (opaque string; the implementation in
  DAS-1454 fixes generation, e.g. a ULID or random token — no new dependency).
- **`parent_span_id`** — the enclosing span's `span_id`, giving the trace tree;
  **`null` for a root span** (a top-level `run` or `wave`). (→ OTel
  `parent_span_id`.)
- **`kind`** — the span kind, exactly one of
  **`{invoke_agent, chat, execute_tool, wave, run}`**. `invoke_agent`, `chat`, and
  `execute_tool` are the OTel GenAI operation names verbatim; `wave` and `run` are
  DasLab orchestration spans (the run/wave envelopes that contain agent work) —
  named consistently so they slot into the same attribute. (→ OTel GenAI
  `gen_ai.operation.name`.)
- **`gen_ai.agent.name`** — the agent/role name (e.g. `"cto"`, `"backend-eng-1"`).
- **`gen_ai.request.model`** — the model/tier the agent ran on (`"opus"` /
  `"sonnet"` / `"haiku"`, or a full model id when available). In DasLab the **tier
  and the model are the same axis** — dispatch is by model per the Model
  Allocation Law — so a single field carries both; there is no separate tier
  field.
- **`start`** / **`end`** — the span's start and end timestamps, **caller-supplied
  ISO-8601 `Z`** (same rule as the event store; never generated inside a pure
  builder). (→ OTel span start/end times.)
- **`duration_ms`** — the **derived** span duration in milliseconds
  (`end - start`). Recorded for convenience/queryability; it is not independent
  state (OTel likewise derives duration from start/end). (→ local
  `daslab.span.duration_ms`.)
- **`gen_ai.usage.input_tokens`** — input token count for this span.
- **`gen_ai.usage.output_tokens`** — output token count for this span.
- **`gen_ai.usage.cached_input_tokens`** — *(optional)* cache-read input token
  count, sourced from the provider's cache-read usage (Anthropic reports this as
  `usage.cache_read_input_tokens`). Omitted / `0` when nothing was served from
  cache.
- **`cached`** — a boolean cache indicator: `true` when any input token was served
  from cache for this span (i.e. `cached_input_tokens > 0`). The always-present,
  cheap-to-query signal; the precise count lives in
  `gen_ai.usage.cached_input_tokens`. (→ local `daslab.usage.cached`.)
- **`status`** — the span outcome, one of **`{ok, error}`**, aligned with the OTel
  span status. (→ OTel span status code `OK` / `ERROR`.)
- **`created_at`** — envelope timestamp, **caller-supplied** (append-only
  discipline; never generated inside a pure builder — consistent with
  `scripts/dgox/events.py`). For a completed span `created_at` typically equals
  `end`, but it is passed explicitly, not inferred.

Example (a root `run` span, cache-warm):

```json
{
  "event_type": "span",
  "ticket_id": "DAS-1453",
  "trace_id": "DAS-1453",
  "span_id": "01J9ZB2K7Q0W9E4R5T6Y7U8ISP",
  "parent_span_id": null,
  "kind": "run",
  "gen_ai.agent.name": "cto",
  "gen_ai.request.model": "opus",
  "start": "2026-07-03T12:00:00Z",
  "end": "2026-07-03T12:03:20Z",
  "duration_ms": 200000,
  "gen_ai.usage.input_tokens": 18450,
  "gen_ai.usage.output_tokens": 5120,
  "gen_ai.usage.cached_input_tokens": 16000,
  "cached": true,
  "status": "ok",
  "created_at": "2026-07-03T12:03:20Z",
  "run_id": "01J9Z8QK3M7Q0W9E4R5T6Y7U8I"
}
```

A child span (e.g. `kind: "execute_tool"`) is identical in shape with a non-null
`parent_span_id` pointing at its enclosing span, and typically no token usage.

### 2. OTel GenAI semantic-convention names are the field names

The field names above **are** the OpenTelemetry GenAI semantic-convention
attribute names wherever a convention exists, so a real OTel exporter is a
field-mapping shim — not a schema change. This mapping table is the **single
authoritative change-point**: if OTel ratifies or renames an attribute, only this
row changes, and only the exporter follows.

| Span field (JSON key)              | OTel attribute / concept                    | Notes |
|------------------------------------|---------------------------------------------|-------|
| `trace_id`                         | `trace_id` (OTel Span core)                 | Ours is a human-readable ticket id; exporter derives the 16-byte hex as a pure function of it. |
| `span_id`                          | `span_id` (OTel Span core)                  | Opaque unique id. |
| `parent_span_id`                   | `parent_span_id` (OTel Span core)           | `null` ⇒ root span. |
| `kind`                             | `gen_ai.operation.name`                     | `invoke_agent` / `chat` / `execute_tool` are OTel GenAI operation names; `wave` / `run` are DasLab extensions. |
| `gen_ai.agent.name`                | `gen_ai.agent.name`                          | Verbatim. |
| `gen_ai.request.model`             | `gen_ai.request.model`                       | Carries the model/tier (opus/sonnet/haiku). |
| `start` / `end`                    | OTel span start / end time                   | ISO-8601 `Z`; exporter converts to unix-nanos. |
| `duration_ms`                      | `daslab.span.duration_ms` (derived)          | OTel derives duration from start/end; kept for local queryability. |
| `gen_ai.usage.input_tokens`        | `gen_ai.usage.input_tokens`                  | Verbatim. |
| `gen_ai.usage.output_tokens`       | `gen_ai.usage.output_tokens`                 | Verbatim. |
| `gen_ai.usage.cached_input_tokens` | `gen_ai.usage.cached_input_tokens`           | From provider cache-read usage; emerging convention — this row is the change-point if it shifts. |
| `cached`                           | `daslab.usage.cached` (local boolean)        | Convenience flag derived from cached-token count. |
| `status`                           | OTel span status code (`OK` / `ERROR`)       | `ok` / `error`. |
| `event_type`, `ticket_id`, `created_at`, `run_id` | store envelope / resource attributes | Envelope stays snake_case per ADR 0011; `run_id` becomes a trace resource/link attribute at export. |

DasLab-specific concepts that have no GenAI attribute are namespaced under
`daslab.*` (never squatting an un-owned `gen_ai.*` name), keeping the vendor
namespace clean and the exporter unambiguous.

### 3. Append-only; caller-supplied timestamps

Spans inherit the ADR 0011 envelope invariants without exception:

- **Append-only.** A span is **never rewritten**. A correction is a **new
  compensating span** (append-only, like the event store), never an in-place edit.
- **Caller-supplied timestamps.** `created_at`, `start`, and `end` are **arguments**
  to the (pure) builder — never `utcnow()` inside a helper — so span builders stay
  deterministic and testable, exactly as `build_routing_decision` /
  `build_agent_invocation` are today. `duration_ms` is derived from the supplied
  `start`/`end` and adds no clock read.
- **New reserved type.** DAS-1454 adds `"span"` to `_VALID_EVENT_TYPES` in
  `scripts/dgox/events.py` and ships the typed builder + validator; until then the
  span shape is spec-only. The store's append path, concurrency guarantees, and
  `iter_events` reader are reused unchanged.

### 4. Reconciliation with `graph_state.trace_ids`

`graph_state.artifacts.trace_ids` (`scripts/dgox/state.py`,
`FIELD_GROUPS["artifacts"]`, sole writer worker/CI) and the span records are **two
sides of the ADR 0011 §1 canonical/derived split**:

- The **span stream** (spans in `board/.events.jsonl`) is the **record of truth**
  for span data — the timings, tokens, tree, and outcomes live there.
- **`graph_state.trace_ids` is a derived mirror of *pointers*** — the
  `trace_id` / `span_id` identifiers that point **at** span records. It holds
  references, never the span payloads themselves.
- On any divergence, the **stream wins** and `trace_ids` is recomputed from it —
  identical to the rule that graph_state is a derived, never-primary mirror of the
  board + event replay (ADR 0011 §1, ADR 0010 C2). `trace_ids` is therefore an
  index/accelerator into the span stream, not an independent store, and its field
  group and sole-writer contract in `state.py` are unchanged by this ADR.

### 5. Approved defaults

Per the Founder-approved ORGANISM defaults (§9, approved 2026-07-03) and the
posture above: the span stream is the WS3 telemetry seam layered on the existing
event store; it changes **no** existing shape, **no** replay/recovery scorer, and
**no** dispatch behavior. Emitting spans is additive and observational (shadow-mode
consistent with ADR 0011 §4 / ADR 0019) — nothing dispatches off a span.

## Consequences

**Positive**

- A run is reconstructable as a **timed parent/child span tree** (`trace_id` =
  ticket id; `parent_span_id` chain), with per-span token and cache accounting —
  the foundation WS3 BRIDGE needs for cost and latency observability.
- A real **OpenTelemetry exporter is a trivial adapter**: the persisted field
  names already are the GenAI semantic-convention names, so `OTLPSpanExporter`
  becomes a field-mapping shim over the §2 table, not a schema migration.
- **No second source of truth.** Spans extend the ADR 0011 event store (same
  envelope, append-only, pure builders, caller-supplied `created_at`); the
  existing store, readers, and replay/recovery scorers keep working unchanged.
- `graph_state.trace_ids` is **explicitly reconciled** as a derived mirror of
  pointers into the canonical span stream — no ambiguity about which side is
  authoritative.

**Negative / accepted**

- Adopting vendor-neutral names **now**, before any OTel SDK is wired, spends
  design effort ahead of the payoff. Accepted — that up-front commitment is
  precisely what makes the future exporter cheap and is the hard-to-reverse call
  this ADR records.
- `gen_ai.usage.cached_input_tokens` tracks an **emerging** OTel attribute; if the
  convention renames it, we carry a mapping-table delta (and, for already-written
  spans, a documented alias). Accepted — the §2 table localizes the change to one
  row, and cache accounting is worth the small risk.
- Dotted `gen_ai.*` JSON keys are slightly less ergonomic than flat snake_case for
  hand-reading. Accepted — the exporter-triviality win outweighs it, and the
  envelope keys stay snake_case.
- `duration_ms` is **derived** and therefore technically redundant with
  `start`/`end`. Accepted — it is a cheap, always-present query convenience, marked
  derived so no reader treats it as independent truth.

**Implementation notes for consumers (not shipped here — DAS-1454)**

- Register `"span"` in `_VALID_EVENT_TYPES` (`scripts/dgox/events.py`) and add a
  pure `build_span(...)` builder + `validate_span(...)` validator matching the §1
  field names and §2 mapping **exactly** (a rename silently breaks the future
  exporter). Builders take `created_at` / `start` / `end` as arguments.
- Enforce: `kind ∈ {invoke_agent, chat, execute_tool, wave, run}`;
  `parent_span_id` null ⇒ root; `status ∈ {ok, error}`; `trace_id == ticket_id`;
  `duration_ms == (end - start)` in ms; `cached == (cached_input_tokens > 0)`.
- Keep `graph_state.trace_ids` a recomputed mirror of pointers into the span
  stream — never a write-through primary.
