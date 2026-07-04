---
id: DAS-1455
title: Dispatch emitter — the missing producer (run_start/run_end/span per dispatch)
status: done
assignee: cto
author: ceo
dept: engineering
priority: p1
parent: DAS-1441
goal: organism-ws3-bridge
depends_on: [DAS-1443, DAS-1454]
zone: scripts/emitter
created: 2026-07-03
updated: 2026-07-03
---

## Description

**AADL stage: GATE-3 Development. THE CRITICAL UNBLOCKER.**

DasLab's whole observability stack (T1–T7 gates, anti-gaming R-9, concurrency/model-mix
KPIs) reads from the DGO-X append-only event store at `board/.events.jsonl`. Today that
store has typed *builders* and *readers* but **no producer** — nothing appends the
`run_start` / `run_end` / span events that a real wave should emit. As a result every
event-based T-gate reads "inert" (returns `None` — a shipped lever with no live data),
because `metrics_lib`/`wave_kpi` find zero paired run events. This ticket builds that
missing producer: the emitter that turns a wave's dispatch/collect data into well-formed
events on the store.

**What & why.** Build a standalone module (e.g. `scripts/dispatch_emitter.py`) that, given
a wave's dispatch/collect data (the per-ticket dispatch records the orchestrator already
has: ticket_id, run_id, model, outcome, PR/CI/T7 evidence, start/end timestamps), appends
to `board/.events.jsonl`, **via the DAS-1443/1454 typed builders**:

- a **`run_start`** event per dispatch,
- a **`run_end`** event per dispatch carrying `metrics_lib`'s exact evidence fields, and
- a **span** per dispatch (one of `invoke_agent` / `execute_tool` / `chat` / `wave` / `run`).

Keep it a **pure function of its inputs** (deterministic, injectable `created_at`, no
`utcnow()` inside the builder path, no clock/network reads in the core) so it is unit-
testable in isolation. The `/daslab-cycle` wiring (DAS-1452) is what *calls* this emitter
at dispatch/collect time — this ticket delivers the callable producer, not the wiring.

**Extend-vs-new posture.** NEW standalone module (`scripts/dispatch_emitter.py`); do NOT
fold this into `scripts/dgox/events.py` (that stays the pure builder/store library) nor
into the cycle skill. REUSE, never re-implement:
- `scripts/dgox/events.py` — `EventStore` (append-only, `fcntl` lock + `O_APPEND` + fsync),
  `validate_envelope`, and the DAS-1443/1454 typed builders for `run_start`/`run_end`/span.
  `run_start`, `run_end` are already in `_VALID_EVENT_TYPES`.
- `scripts/metrics_lib.py` — the EXACT field names the `run_end` payload must carry so the
  downstream checks compute a real number (see below).
- `scripts/wave_kpi.py` — `busy_fraction_from_events()` / `read_events()`: pairs
  `[run_start, run_end]` intervals **by `run_id`** and counts `model` **once per
  `run_start`**. The emitter's output must satisfy this pairing (every `run_start.run_id`
  has a matching `run_end.run_id`; both carry `created_at` as `YYYY-MM-DDTHH:MM:SSZ`).

**Exact `run_end` payload fields (from `scripts/metrics_lib.py`) — copy verbatim:**
- `outcome` — success vocabulary is `{"success","ok","passed","done"}`; anything else
  (error/timeout/no_work/failed) is NOT a success (`_is_successful_completion`).
- `model` — lowercased model name; `LOW_COST_MODELS = {"haiku"}` feeds T4 `model_mix`.
- `merged_pr` — truthy → counts toward R-9 (`gaming_violations`).
- `ci_status` — must be in `GREEN_CI = {"green","pass","passed","success"}` for R-9.
- `t7_pass` — robust truthy flag (`TRUE_VALUES = {"true","pass","passed","1","yes","ok"}`).
- `t7_score` — float; `t1b_high_impact` needs `>= 0.90`.
Plus the envelope: `event_type`, `ticket_id` (`DAS-` prefixed), `created_at`, and `run_id`
(the join key across `run_start`/`run_end`/span). `run_end` must set `event_type:"run_end"`.

**Key existing files this ticket touches (paths):**
- `scripts/dispatch_emitter.py` — NEW (this ticket's deliverable).
- `scripts/dgox/events.py` — imported (builders + `EventStore`); NOT modified here.
- `scripts/metrics_lib.py` — field-name source of truth; NOT modified.
- `scripts/wave_kpi.py` — pairing/consumer contract; NOT modified.
- tests under the emitter's zone (`scripts/emitter` / repo test dir) — NEW.

**Do NOT flip `dgox_emit`.** Turning the producer on for real waves is a governance flag
flip done at wiring time (DAS-1452), not here. This ticket only makes the producer exist
and be correct; the store stays in shadow mode until the wiring ticket flips the flag.

**Consumes:** `typed-run-events` (DAS-1443), `span-builder` (DAS-1454).
**Produces:** `dispatch-emitter` (consumed by DAS-1452 wiring and DAS-1456).

## Acceptance criteria

- [ ] A new standalone module `scripts/dispatch_emitter.py` exists whose core is a **pure
      function of its inputs** (dispatch/collect records in → events out; `created_at`
      injectable; no clock/network read in the core path).
- [ ] For each dispatch it appends a `run_start`, a `run_end`, and a span
      (`invoke_agent`/`execute_tool`/`chat`/`wave`/`run`) built via the DAS-1443/1454
      **typed builders** — never hand-rolled dicts — and every event passes
      `events.validate_envelope` (correct `event_type`, `DAS-`-prefixed `ticket_id`,
      non-empty `created_at`, non-empty `run_id`).
- [ ] The `run_end` payload carries the EXACT `metrics_lib` field names:
      `outcome`, `model`, `merged_pr`, `ci_status`, `t7_pass`, `t7_score` (verified against
      `scripts/metrics_lib.py`).
- [ ] Each dispatch's `run_start` and `run_end` share the same `run_id`, and every
      `run_start` has a matching `run_end`, so `wave_kpi.busy_fraction_from_events` pairs
      them and counts `model` once per run.
- [ ] A synthetic wave input (fixture) yields events for which
      `check_busy_fraction` / `check_concurrency` (`metrics_lib.concurrency_stats`) /
      `check_model_mix` (`metrics_lib.model_mix`) each compute a **real number** (not
      `None`) — asserted in a test.
- [ ] The emitter is **append-only**: it uses `EventStore.append` and never truncates,
      rewrites, or edits existing lines in `board/.events.jsonl`.
- [ ] Unit tests cover: envelope validity, exact `run_end` fields, run_start/run_end
      `run_id` pairing, span emission, append-only behaviour, and the "downstream metric
      is non-`None`" invariant. Tests write to a `tmp_path` store, not the live store.
- [ ] The module does NOT flip `dgox_emit` and does NOT modify `events.py`,
      `metrics_lib.py`, or `wave_kpi.py`.
- [ ] Frontmatter carries NO `project:` field (org-engine work; `board_lint` R9).

## Log

### 2026-07-03 — CEO
Created from ORGANISM program-plan decomposition (/daslab-plan). Spec-of-record: docs/research/ORGANISM-PROGRAM-PLAN.md.

### 2026-07-03 — Backend EM
Built the missing DGO-X event PRODUCER — `scripts/dispatch_emitter.py` (NEW, standalone; `events.py`/`metrics_lib.py`/`wave_kpi.py` NOT modified).

**Emitter API.** `DispatchRecord` (frozen dataclass — the per-dispatch/collect input the orchestrator already holds: ticket_id, run_id, goal, engine_version, model, role_key, start/end ISO-8601 Z, outcome, merged_pr, ci_status, t7_pass, t7_score, span_kind; optional span/token/timestamp overrides). Pure core:
- `build_dispatch_events(record) -> [run_start, run_end, span]` — deterministic, no clock/network read; built via the DAS-1443/1454 typed builders `build_run_start`/`build_run_end`/`build_span` (never hand-rolled) and validated by `validate_run_start`/`validate_run_end`/`validate_span` before return.
- `build_wave_events(records)` — flattens a wave in dispatch order.
- `emit_dispatch(record, *, store|store_path)` / `emit_wave(records, ...)` — append-only via `EventStore.append` (never truncate/rewrite). Default store = live `board/.events.jsonl`; tests always pass a `tmp_path` store.

`run_start`/`run_end` share `run_id` (pairing contract); `run_end` carries the EXACT `metrics_lib` field set (`RUN_END_METRICS_FIELDS`): outcome, model, merged_pr, ci_status, t7_pass, t7_score. **`dgox_emit` NOT flipped** — producer exists + is correct; store stays shadow until DAS-1452 wiring.

**Metrics-go-live proof.** New `tests/test_dispatch_emitter.py` (15 tests): a synthetic 4-run overlapping wave (mixed haiku/sonnet/opus) makes all three previously-inert event-based gates compute a REAL number — `wave_kpi.busy_fraction_from_events` (T1) ≠ None, `metrics_lib.concurrency_stats` (T3) median > 1, `metrics_lib.model_mix` (T4) ratio 0.5 — and drives the actual `check_busy_fraction`/`check_concurrency`/`check_model_mix` `main(argv)` CLIs to exit 0 on that store. Ends the false-green "unmeasured" state. Also covers envelope validity, exact run_end fields, run_id pairing, span emission, append-only (byte-prefix invariant), determinism, iter_events replay.

**Shadow-clean.** Added `"dispatch_emitter.py"` to `_EVENT_PRODUCERS` in `tests/test_dgox_phase1_shadow.py` (precedent: pulse_checkpoint.py) — it is a write-only PRODUCER, never reads events to route.

**Verify (full suite):** pytest 960 passed / 1 skipped; diagnostics 100/100; board_lint 0; `ruff check scripts tests` clean. Committed local-only on `feat/das-1455-dispatch-emitter`. → `status: in_review`, assignee `cto` (never review own work). No push/PR (local-only per orchestrator).

### 2026-07-03 — Orchestrator (/daslab-cycle collect)
Done via local-only done-gate: full suite 993 pass + validators green + merge verification. dispatch_emitter.py: build_dispatch_events -> [run_start,run_end,span]; run_end carries exact metrics_lib fields; synthetic wave makes check_busy_fraction(T1)/concurrency(T3)/model_mix(T4) compute REAL numbers (false-green fixed). Added to _EVENT_PRODUCERS.
