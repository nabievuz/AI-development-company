---
id: DAS-1443
title: Typed run_start/run_end/wave/checkpoint builders + validators in dgox/events.py
status: done
assignee: cto
author: ceo
dept: engineering
priority: p1
parent: DAS-1440
goal: organism-ws1-pulse
depends_on: [DAS-1442]
zone: scripts/dgox
created: 2026-07-03
updated: 2026-07-03
---

## Description

**What.** Add four typed event builders and their validators to the DGO-X
append-only event store, `scripts/dgox/events.py`:

- `build_run_start` / `validate_run_start`
- `build_run_end` / `validate_run_end`
- `build_wave` / `validate_wave`
- `build_checkpoint` / `validate_checkpoint`

and register any of these `event_type` strings that are not already in the
module's `_VALID_EVENT_TYPES` frozenset.

**Why.** This is the WS1-Pulse (ORGANISM program) work that gives the event
store first-class, self-validating shapes for the run lifecycle. Today the
store only ships two load-bearing typed shapes — `routing_decision` (Shape A)
and `agent_invocation` (Shape B) — while the downstream metrics layer,
`scripts/metrics_lib.py`, already reads `run_start` / `run_end` events by hand
(see `run_intervals`, `model_mix`, `gaming_violations`, `t1b_high_impact`).
Without typed builders, those `run_end` events are hand-assembled at every call
site, so a single mis-spelled or missing field silently breaks T3 concurrency,
T4 model-mix, R-9 anti-gaming, and T1b high-impact. Typed builders + a
conformance test make the producer/consumer contract explicit and enforced.

**Extend-vs-new posture: EXTEND `scripts/dgox/events.py` in place.** Do NOT
create a new module. Follow the two existing shapes exactly — same file, same
section-comment structure (`# ---- Shape … ----`), same `build_*` /
`validate_*` naming, same keyword-only signatures, same "envelope-first"
validation pattern (each `validate_*` calls `validate_envelope(event)` first and
appends shape-specific errors). Mirror the docstring density of the existing
builders.

**Load-bearing contract with `scripts/metrics_lib.py` (read it before coding).**
`run_end` MUST carry the exact field names the metrics layer already reads —
renaming any of these silently zeros out a KPI:

- `run_id` — join key; `run_intervals` pairs `run_start`/`run_end` by it, and
  `model_mix` de-dups per unit via `_unit_key` (`run_id` or `ticket_id`).
- `created_at` — parsed by `_parse_iso` (`"%Y-%m-%dT%H:%M:%SZ"`) for T3 intervals.
- `outcome` — `_is_successful_completion` lower-cases it; success vocabulary is
  `SUCCESS_OUTCOMES = {"success","ok","passed","done"}`; empty counts as success.
- `model` — `model_mix` lower-cases it and tests membership in
  `LOW_COST_MODELS = {"haiku"}`.
- `merged_pr` — `gaming_violations` requires it truthy (R-9 "no merged PR").
- `ci_status` — must be in `GREEN_CI = {"green","pass","passed","success"}`.
- `t7_pass` — `_is_true_flag` truthiness (a string `"false"`/`"no"`/`"0"` fails).
- `t7_score` — `t1b_high_impact` compares `float(t7_score) >= 0.90`.

`run_end` is treated as a completion event by `_is_completion_event`
(`event_type == "run_end"`), so all of the above evidence fields ride on it.

**Determinism / append-only discipline (from the module header + ADR 0011).**
`created_at` stays a **caller-supplied argument** — never call `utcnow()` inside
a pure builder/validator (callers pass a timestamp so helpers stay deterministic
and unit-testable). The store is **append-only, never rewritten**: a correction
is a new *compensating* event, never an in-place edit of a prior line. Do not
add any code path that mutates or rewrites existing events.

**Key existing files this ticket touches / depends on:**

- `scripts/dgox/events.py` — the module to extend (builders, validators,
  `_VALID_EVENT_TYPES`). Note `run_start` and `run_end` are ALREADY listed in
  `_VALID_EVENT_TYPES` (as reserved types); `wave` and `checkpoint` are NOT —
  add the missing ones only.
- `scripts/metrics_lib.py` — the downstream consumer that fixes the `run_end`
  field contract (read-only reference; do not modify in this ticket).
- `tests/test_dgox_events.py` — the pytest suite to extend with mirrored tests.

## Acceptance criteria

- [ ] Typed builders + validators exist in `scripts/dgox/events.py` for all four
      types: `build_run_start`/`validate_run_start`,
      `build_run_end`/`validate_run_end`, `build_wave`/`validate_wave`,
      `build_checkpoint`/`validate_checkpoint`.
- [ ] Each `validate_*` calls `validate_envelope` first (envelope-first pattern),
      then appends shape-specific errors, and pins the correct `event_type`
      (mirrors `validate_routing_decision` / `validate_agent_invocation`).
- [ ] `build_run_end` emits ALL of the exact field names `scripts/metrics_lib.py`
      reads: `run_id`, `created_at`, `outcome`, `model`, `merged_pr`,
      `ci_status`, `t7_pass`, `t7_score` (plus `event_type` and `ticket_id`).
- [ ] Field names match `metrics_lib` exactly — a **conformance test** is added
      that asserts a `build_run_end(...)` event satisfies the metrics readers
      (e.g. it flows through `model_mix` / `gaming_violations` /
      `t1b_high_impact` / `run_intervals` and is counted, not silently dropped),
      so any future rename breaks a test.
- [ ] `created_at` remains a required caller-supplied argument on every new
      builder; no new builder/validator calls `utcnow()` internally.
- [ ] `_VALID_EVENT_TYPES` includes `run_start`, `run_end`, `wave`, `checkpoint`
      (add `wave`/`checkpoint`; `run_start`/`run_end` already present).
- [ ] Unit tests mirroring `tests/test_dgox_events.py` are added for each new
      shape: build-produces-expected-shape, mutation-copy safety where a
      collection/dict arg is used, valid-event-no-errors, wrong-event-type error,
      and at least one missing/invalid-field error per shape.
- [ ] No in-place event rewrites: builders return fresh dicts; corrections are
      modeled as new compensating events (no mutation path added to the store).
- [ ] `pytest tests/test_dgox_events.py` is green (and the full suite is not
      regressed).

## Log

### 2026-07-03 — CEO
Created from ORGANISM program-plan decomposition (/daslab-plan). Spec-of-record:
docs/research/ORGANISM-PROGRAM-PLAN.md.

AADL stage: GATE-2/3.
Consumes: adr-0023.
Produces: typed-run-events (consumed by DAS-1444 / DAS-1451 / DAS-1454 /
DAS-1455 / DAS-1456).

### 2026-07-03 — Backend EM
Implemented the four typed shapes + validators in `scripts/dgox/events.py`
(EXTENDED in place, no new module), mirroring the existing Shape A/B pattern
(keyword-only builders, envelope-first validators, caller-supplied `created_at`,
defensive copies of collection/dict args, fresh dicts — append-only, no mutation
path):

- Shape C `build_run_start`/`validate_run_start` — `run_id, goal, engine_version`
  (+ envelope `event_type, ticket_id, created_at`).
- Shape D `build_run_end`/`validate_run_end` — LOAD-BEARING metrics contract:
  emits the EXACT names `scripts/metrics_lib.py` reads —
  `run_id, created_at, outcome, model, merged_pr, ci_status, t7_pass, t7_score`
  (+ `event_type, ticket_id`). Single source of truth exported as
  `RUN_END_METRICS_FIELDS`; `validate_run_end` flags any missing contract field
  and non-float `t7_score`.
- Shape E `build_wave`/`validate_wave` — `wave (1-based int), tickets (list)`,
  optional `routing` (mirrors `manifest.json.waves[]`).
- Shape F `build_checkpoint`/`validate_checkpoint` — `wave, board_hash,
  event_offset, ticket_states (delta), pending_interrupts, ledger_hashes{prev,self}`
  (mirrors `wave-NNN.checkpoint.json`, ADR 0023 §2/§3).

Registered `wave` + `checkpoint` in `_VALID_EVENT_TYPES` (`run_start`/`run_end`
were already reserved).

Tests (`tests/test_dgox_events.py`): added `TestRunStart`, `TestRunEnd`,
`TestWave`, `TestCheckpoint`, `TestNewShapesRoundTrip`, and a
`TestRunEndMetricsConformance` **schema-conformance** class asserting a
`build_run_end(...)` event flows through and is COUNTED by `model_mix` (haiku
low-cost), `gaming_violations` (full evidence ⇒ no violation; stripped evidence
⇒ flagged), `t1b_high_impact` (t7_score ≥ 0.90), and `run_intervals`
(run_start/run_end paired by `run_id`) — so any future field rename breaks a
test. Each new shape also has build-shape, mutation-copy safety,
valid-no-errors, wrong-event-type, and missing/invalid-field cases.

VERIFY (all green): `python3 scripts/diagnostics.py` = 100/100;
`python3 scripts/board_lint.py` = 0 violations (17 tickets);
`python3 -m pytest tests/test_dgox_events.py -q` = 81 passed;
full suite `python3 -m pytest -q` = 763 passed, 1 skipped (no regression);
`ruff check scripts tests` clean.

Committed LOCAL-ONLY to `feat/das-1443-typed-event-builders` (no push, no PR per
ORGANISM LOCAL-ONLY git strategy). Status → in_review; routed to CTO (manager)
for GATE-3 review — I authored this, so I do not review it.

### 2026-07-03 — Orchestrator (/daslab-cycle collect)
Done via local-only done-gate: green diagnostics(100/100)/board_lint/pytest(810) + combined-merge verification (pure-code review collapsed into orchestrator+validator verification per local-only strategy). Typed run_start/run_end/wave/checkpoint builders; run_end matches metrics_lib exactly (conformance test). Merged to local main; combined suite 810 pass.
