---
id: DAS-1441
title: ORGANISM WS3 — BRIDGE (observability & cost) — slice 1 emitter seam
status: done
assignee: cto
author: ceo
dept: engineering
priority: p1
parent: 
goal: organism-ws3-bridge
created: 2026-07-03
updated: 2026-07-03
---

## Description

**EPIC — Observability & cost substrate (WS3 BRIDGE), slice 1: the emitter seam.**
This epic delivers the telemetry substrate that kills the two v1.0.0 capability
gaps **G5 (untyped telemetry)** and **G6 (no cost metering)** and re-derives the
clean-room patterns **P11 (OTel-named spans), P12 (cost-ledger), P13 (committed
evidence)**. Spec-of-record: [`docs/research/ORGANISM-PROGRAM-PLAN.md`](../../docs/research/ORGANISM-PROGRAM-PLAN.md)
**§4 WS3** (the BRIDGE table O3-T01…O3-T07) plus §0 executive summary and §6
risk register items 1, 2, 8.

**THIS SLICE (slice 1) delivers only the emitter seam** — the shared substrate
the audit calls "the highest-leverage single asset in the entire program":

1. **ADR-0024 span schema** — OTel GenAI semconv attribute *names*
   (`gen_ai.agent.name`, `gen_ai.usage.input_tokens`, …) written as JSONL,
   adapter-ready. (plan O3-T01)
2. **Typed `run_start` / `run_end` + span builders + validators** added to
   `scripts/dgox/events.py`. (plan O3-T02, shared with WS1 O1-T02)
3. **The missing dispatch emitter** — instrument `/daslab-cycle` step 5 so a real
   wave appends paired `run_start` / `run_end` + span events per ticket. This is
   the producer that today does not exist. (plan O3-T03)
4. **Metric recompute-from-spans** — `wave_kpi.py` + the T1–T7 validators derive
   their KPIs from spans via a single `read_events` source of truth. (plan O3-T07)

The **cost-ledger (P12 / O3-T04), alerting (O3-T05), and committed-evidence
(P13 / O3-T06)** tickets are explicitly **out of scope for this slice** — they
land in **slice 2**. Because of that split, **full WS3 AADL gate closure spans
both slices**: slice 1 closes the Planning + Design + emitter-Dev increment; the
WS3 epic gate is only fully closed once slice 2 lands cost/alerting/evidence.

**CRUX (state this precisely — it is the whole reason this ticket exists).**
Today the observability layer is a *false green*:

- `board/.events.jsonl` **does not exist** and **no production code emits
  `run_start` / `run_end`**. No live wave has ever produced a paired run event,
  so every T1–T7 gate is currently **inert** ("false green").
- `scripts/dgox/events.py` **reserves** `run_start` and `run_end` in
  `_VALID_EVENT_TYPES` (lines 108–122) but has **NO typed builder and NO
  validator** for them — only `routing_decision` and `agent_invocation` have
  typed `build_*` / `validate_*` helpers.
- `scripts/metrics_lib.py` **already reads** an extended `run_end` schema:
  - `run_intervals()` / `concurrency_stats()` (T3) key off
    `event_type == "run_start"` / `"run_end"` + `run_id` + `created_at`.
  - `model_mix()` (T4) reads `run_end.outcome` and `run_end.model`.
  - `gaming_violations()` (R-9) reads `merged_pr`, `ci_status`, `t7_pass`.
  - `t1b_high_impact()` reads `t7_pass` + `t7_score`.
  - `recovery_reliability()` (T5) reads `recovery_drill.outcome` +
    `recovery_drill.corrupted`.
- **The emitter MUST match those exact field names** —
  `run_end.{outcome, model, merged_pr, ci_status, t7_pass, t7_score}` and
  `recovery_drill.{outcome, corrupted}` — or every T-gate stays inert and the
  §5 v2.0 release contract cannot go green (risk-register items 1 & 2:
  false-green metrics + schema drift).

**Extend-vs-new posture** (from plan §3 inventory — do NOT duplicate):
- `scripts/dgox/events.py` → **extend**: add typed `build_run_start` /
  `build_run_end` / `build_span` + `validate_*`; keep the existing envelope
  helpers, `EventStore`, `iter_events`, and the caller-supplied `created_at`
  discipline unchanged (append-only; corrections are compensating events).
- `scripts/wave_kpi.py` → **extend**: reuse its `read_events()` /
  `busy_fraction_from_events` as the single source of truth.
- `scripts/metrics_lib.py` → **extend / conform-to**: it is the *de-facto
  schema*; the emitter conforms to it, it is not rewritten.
- The dispatch emitter in `/daslab-cycle` step 5 → **new** producer code.
- ADR-0024 → **new** doc; add a row to `docs/adr/README.md`.

**Key existing files this ticket touches (with paths):**
- `scripts/dgox/events.py` — add typed run/span builders + validators; the
  reserved types live at lines 108–122.
- `scripts/metrics_lib.py` — the binding field-name contract (read-only here;
  emitter must match; T3/T4/T5/R-9 functions listed above).
- `scripts/wave_kpi.py` — shared `read_events()` recompute source.
- `.claude/skills/daslab-cycle/SKILL.md` — step 5 dispatch is where the emitter
  is wired (preserve the 4 skill-token-tested selection guards verbatim).
- `docs/adr/` + `docs/adr/README.md` — ADR-0024 + index row.
- `tests/test_dgox_events.py` — extend with schema-conformance tests.
- `scripts/diagnostics.py` — must stay 100/100 after the change.

**Constraints (binding):** append-only store (a correction is a new
compensating event); `created_at` is ALWAYS caller-supplied, never generated
inside a pure builder; the T7 rubric is immutable; anti-gaming R-9 stands
(counted work needs `merged_pr` + green `ci_status` + `t7_pass`). This is
**org-engine work** — the frontmatter carries **NO `project:` field**
(board_lint R9); do not place anything under `projects/`.

**Children in this slice:** DAS-1453, DAS-1454, DAS-1455, DAS-1456.

## Acceptance criteria

- [ ] **ADR-0024 span schema merged** — documents the OTel GenAI semconv
      attribute *names* (`gen_ai.agent.name`, `gen_ai.usage.input_tokens`,
      `gen_ai.usage.output_tokens`, span kind, `trace_id`/`span_id`/
      `parent_span_id`, `cached`, `status`, tier) as the JSONL span shape;
      adapter-ready; a row is added to `docs/adr/README.md`.
- [ ] **Typed builders exist and are validated** — `build_run_start`,
      `build_run_end`, and `build_span` (plus their `validate_*` functions) are
      added to `scripts/dgox/events.py`; `run_start` / `run_end` remain in
      `_VALID_EVENT_TYPES`; a span event type is registered.
- [ ] **Field names match `metrics_lib.py` EXACTLY** — the `run_end` builder
      emits `outcome`, `model`, `merged_pr`, `ci_status`, `t7_pass`, `t7_score`
      (and paired `run_start`/`run_end` share a `run_id` + ISO-8601
      `YYYY-MM-DDTHH:MM:SSZ` `created_at`); a schema-conformance test asserts
      `metrics_lib.model_mix`, `concurrency_stats`, `gaming_violations`, and
      `t1b_high_impact` read the builder's output correctly.
- [ ] **The dispatch emitter is wired** — `/daslab-cycle` step 5 appends a
      paired `run_start` + `run_end` and per-ticket `span` events for every
      dispatched ticket; `board/.events.jsonl` is created on first live wave.
- [ ] **A real wave produces paired events** — running one actual wave yields
      paired `run_start`/`run_end` with matching `run_id`s plus well-formed
      span events (no orphan starts/ends).
- [ ] **`wave_kpi` + the T-validators recompute from spans** — KPIs derive from
      the span/event store via a single `read_events` source of truth (T1/T3/T4
      leave "inert" once real events exist).
- [ ] **`pytest tests/test_dgox_events.py` is green** including the new
      run/span builder + validator + schema-conformance tests.
- [ ] **`scripts/diagnostics.py` stays 100/100** (all 8 buckets PASS).
- [ ] **No QONUN/scope violation** — no `project:` field in this ticket, no file
      under `projects/`, `scripts/board_lint.py` passes (R9), and the store stays
      append-only.
- [ ] **Slice boundary recorded** — the epic note explains that cost-ledger,
      alerting, and committed-evidence are slice 2, so full WS3 AADL gate closure
      spans both slices.

## Log

### 2026-07-03 — CEO
Created from ORGANISM program-plan decomposition (/daslab-plan). Spec-of-record: docs/research/ORGANISM-PROGRAM-PLAN.md.

### 2026-07-03 — Orchestrator (/daslab-run)
Epic closed. ORGANISM WS3 BRIDGE slice-1 (emitter seam) CLOSED. ADR-0024 span schema (OTel gen_ai.* names); build_span/validate_span; the dispatch emitter (the missing producer — makes T1/T3/T4 compute REAL numbers, ending 'false-green'); wave_kpi/T-validators recompute from spans + check_spans.py. Children DAS-1453/1454/1455/1456 all done. Slice-2 (cost-ledger, alerting, committed-evidence) + the shadow-rule ADR remain.
