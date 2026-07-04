---
id: DAS-1454
title: Span-events builder/validator (gen_ai.* attrs) in dgox/events.py (P11)
status: done
assignee: cto
author: ceo
dept: engineering
priority: p1
parent: DAS-1441
goal: organism-ws3-bridge
depends_on: [DAS-1453, DAS-1443]
zone: scripts/dgox
created: 2026-07-03
updated: 2026-07-03
---

## Description

**What & why.** The ORGANISM program (spec-of-record: `docs/research/ORGANISM-PROGRAM-PLAN.md`,
workstream WS3 "bridge") needs DasLab runs to emit OpenTelemetry-compatible **spans** so an
agent invocation can be traced across the org with standard `gen_ai.*` semantic-convention
attribute names. Today `scripts/dgox/events.py` (the DGO-X Phase-1 append-only JSONL event
store, ADR 0011) knows two load-bearing shapes — `routing_decision` and `agent_invocation` —
plus reserved envelope types. It does **not** yet know how to build or validate a *span* event.
This ticket adds that shape per **ADR-0024** so downstream tickets (DAS-1455/1456) can emit and
consume typed spans.

**Extend-vs-new posture: EXTEND, do not create a new module.** The span builder/validator lives
**inside the existing `scripts/dgox/events.py`**, mirroring the exact structure already used for
`build_routing_decision`/`validate_routing_decision` and `build_agent_invocation`/`validate_agent_invocation`:
a `frozenset` of required fields, a keyword-only `build_span(...)` helper that returns a plain
`dict`, and a `validate_span(event) -> list[str]` that calls `validate_envelope` first then adds
shape-specific checks. Do NOT invent a new file, class, or parallel store — reuse `EventStore`,
`iter_events`, `validate_envelope`, and the caller-supplied `created_at` discipline verbatim.

**Key existing files this touches (with paths):**
- `scripts/dgox/events.py` — ADD `build_span` + `validate_span`; REGISTER the new span event
  type(s) in the module-level `_VALID_EVENT_TYPES` frozenset (currently at lines ~108-122) so
  `validate_envelope` accepts them (otherwise every span fails the envelope's
  "unknown event_type" check and `EventStore.append` raises `ValueError`).
- `tests/test_dgox_events.py` — ADD a `TestSpan` class mirroring `TestRoutingDecision` /
  `TestAgentInvocation` (a `_make_span_event(**overrides)` factory with a `FIXED_TS` default,
  build-shape assertions, valid-case + malformed-case validation, and an append→`iter_events`
  round-trip through `tmp_path`).
- `scripts/dgox/state.py` — READ ONLY for context (`trace_ids` is the artifacts-group field that
  links a ticket's state to span/trace events); do NOT modify `state.py` in this ticket.
- Spec-of-record: `docs/research/ORGANISM-PROGRAM-PLAN.md`; contract: **ADR-0024**.

**Span shape (OTel `gen_ai.*` semantic conventions, per ADR-0024).** `build_span` must be a
keyword-only helper producing a dict whose envelope keys are `event_type`, `ticket_id`,
`created_at` (+ optional `run_id`) and whose span payload carries, using the standard names:
- `trace_id` = the **ticket id** (a run is traced under its ticket — matches the P4 run_id join
  key discipline; ADR-0024 fixes `trace_id := ticket`).
- `span_id` — this span's id (non-empty string).
- `parent_span_id` — parent span id, or `None` for a root span.
- `gen_ai.operation.kind` (the span **kind**) — the registered span type (see below).
- `gen_ai.request.model` **tier** — the model tier for this span (e.g. opus/sonnet/haiku).
- `start` / `end` — ISO-8601 timestamps (caller-supplied; never generated inside the pure helper).
- `duration` — elapsed time for the span.
- `gen_ai.usage.input_tokens` / `gen_ai.usage.output_tokens` — token counts.
- `cached` — boolean, whether the call was served from cache.
- `status` — span completion status (e.g. `ok` / `error`).

Follow ADR-0024 for the exact attribute-key spelling; the list above is the required content set.
Use the `gen_ai.*` OTel attribute names (not ad-hoc names). `created_at` stays **caller-supplied**
(injectable for deterministic tests — do NOT call `utcnow()` inside `build_span`), and the store
stays **append-only** (a correction is a new compensating event, never a rewrite).

**Register the kind(s).** Add the span event type(s) to `_VALID_EVENT_TYPES` so the envelope
validator accepts them and `EventStore.append` will write them. Keep the frozenset the single
source of truth for valid types.

## Acceptance criteria

- [ ] `scripts/dgox/events.py` gains a keyword-only `build_span(...)` that returns a dict using
      OpenTelemetry `gen_ai.*` attribute names and carrying: `trace_id` (= ticket id), `span_id`,
      `parent_span_id`, kind, tier, `start`, `end`, `duration`, input tokens, output tokens,
      `cached`, and `status`, per ADR-0024.
- [ ] `created_at` is caller-supplied (a parameter, injectable for tests); `build_span` never
      calls `utcnow()` internally; the store remains append-only.
- [ ] `scripts/dgox/events.py` gains `validate_span(event) -> list[str]` that calls
      `validate_envelope` first, then adds span-specific checks, returning `[]` for a well-formed
      span and a non-empty list of error strings for a malformed one (mirroring the existing
      `validate_routing_decision` / `validate_agent_invocation` pattern; never raises).
- [ ] The span event type(s) are registered in `_VALID_EVENT_TYPES`, so a span passes
      `validate_envelope` and `EventStore.append(span)` succeeds (does not raise "unknown event_type").
- [ ] `tests/test_dgox_events.py` gains a `TestSpan` class mirroring the existing shape tests: a
      `_make_span_event` factory, build-shape assertions, a valid-span-validates case, at least one
      malformed-span-is-rejected case, and an append→`iter_events` round-trip via `tmp_path`
      (never touching the real `board/.events.jsonl`).
- [ ] A well-formed span validates (`validate_span` returns `[]`); malformed spans (missing/blank
      required span fields, wrong `event_type`, bad token/`cached`/`status` types) are rejected.
- [ ] `python3 -m pytest tests/test_dgox_events.py` is green (all existing tests still pass; new
      span tests pass).
- [ ] AADL stage GATE-3 Development satisfied: no `project:` field in frontmatter (org-engine
      work; `board_lint` R9); only `scripts/dgox/events.py` and `tests/test_dgox_events.py` are
      modified.

## Log

### 2026-07-03 — CEO
Created from ORGANISM program-plan decomposition (/daslab-plan). Spec-of-record: docs/research/ORGANISM-PROGRAM-PLAN.md.

AADL stage: GATE-3 Development. Consumes: adr-0024, typed-run-events (DAS-1453/DAS-1443). Produces: span-builder (consumed by DAS-1455/1456). Extends scripts/dgox/events.py in-place following the routing_decision / agent_invocation builder+validator pattern; registers span kind(s) in `_VALID_EVENT_TYPES`; tests mirror tests/test_dgox_events.py.

### 2026-07-03 — Backend EM
Built the span shape (Shape H) per ADR-0024 — EXTEND, in `scripts/dgox/events.py` only, mirroring the existing builder+validator pattern. No new module/class/store.

- Registered `"span"` in the module-level `_VALID_EVENT_TYPES` frozenset (so `validate_envelope` accepts it and `EventStore.append` writes it).
- Added keyword-only `build_span(...)` returning a plain dict with the OTel GenAI semantic-convention names as JSON keys. `trace_id` is derived (:= `ticket_id`), `duration_ms` is derived (:= `end - start` in ms, pure — no clock read), and `cached` is derived (:= `cached_input_tokens > 0`). `created_at`/`start`/`end` are caller-supplied (injectable; no `utcnow()` inside). Optional `run_id`.
- Added `validate_span(event) -> list[str]` (envelope-first, never raises): pins `event_type == "span"`, `trace_id == ticket_id`, non-empty `span_id`, `parent_span_id` null(root)-or-non-empty-string, `kind ∈ {invoke_agent,chat,execute_tool,wave,run}`, `status ∈ {ok,error}`, non-empty `gen_ai.agent.name`/`gen_ai.request.model`, non-empty `start`/`end`, non-negative-int `duration_ms` equal to derived `end - start`, non-negative-int token counts, and `cached == (cached_input_tokens > 0)`.
- Exposed `SPAN_KINDS`, `SPAN_STATUSES`, `SPAN_OTEL_ATTRS` (mapping single-source-of-truth), `_SPAN_REQUIRED`.
- Tests: added `TestSpan` (+ `_make_span_event` factory) to `tests/test_dgox_events.py` — build-shape, OTel-name mapping asserted (and no ad-hoc alias leaks), derived-field checks, all-kinds/all-statuses valid, and ~15 malformed-rejection cases, plus a root→child append→`iter_events` round-trip via `tmp_path`.

OTel name mapping (JSON key → OTel attr): `kind`→`gen_ai.operation.name`; `gen_ai.agent.name`→verbatim; `gen_ai.request.model`→verbatim (carries tier/model, one axis); `gen_ai.usage.input_tokens`/`output_tokens`/`cached_input_tokens`→verbatim; `trace_id`/`span_id`/`parent_span_id`→OTel Span core; `duration_ms`→`daslab.span.duration_ms` (derived); `cached`→`daslab.usage.cached`; `status`→OTel span status (OK/ERROR).

VERIFY (all green): `pytest tests/test_dgox_events.py` = 104 passed; `ruff check scripts tests` = clean; `diagnostics.py` = 100/100; `board_lint.py` = 0 violations. Files touched: `scripts/dgox/events.py`, `tests/test_dgox_events.py` only.

Status → in_review; assignee → cto (my manager; never self-review — I authored the code). LOCAL-ONLY per ORGANISM policy: committed on branch feat/das-1454-span-events, no push/PR.

Routing: CTO to review (GATE-3). Downstream DAS-1455/1456 can now emit/consume typed spans.

### 2026-07-03 — Orchestrator (/daslab-cycle collect)
Done via local-only done-gate: full suite 945 pass + all validators green + combined-merge verification (events.py/SKILL union resolved). build_span/validate_span with OTel gen_ai.* names + SPAN_OTEL_ATTRS mapping; span registered.
