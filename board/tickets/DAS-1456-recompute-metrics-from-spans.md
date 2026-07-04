---
id: DAS-1456
title: wave_kpi + T-validators recompute from spans (single read_events source)
status: done
assignee: backend-em
author: ceo
dept: engineering
priority: p1
parent: DAS-1441
goal: organism-ws3-bridge
depends_on: [DAS-1454, DAS-1455]
zone: scripts/metrics
created: 2026-07-03
updated: 2026-07-03
branch: feat/das-1456-recompute-spans
---

## Description

**What & why.** DasLab's throughput KPIs (`wave_kpi.py`) and the T1–T7
validators (`scripts/metrics_lib.py` + the busy-fraction/gate readers) each
reconstruct their own view of "what ran" — some parse the human-readable
`board/.wave-log`, some read the DGO-X JSONL event store
(`board/.events.jsonl`). DAS-1455 introduces a **span/run event model** written
by the dispatch emitter (the `span-builder` + `dispatch-emitter` this ticket
consumes). This ticket makes **every** metric reader derive from that ONE
source: the shared `read_events` reader over the span/run events. No reader may
keep a private, divergent notion of a run. This is the "single source of truth"
seam that lets slice-2's cost ledger reconcile against the same spans without a
second parse path.

**AADL stage.** GATE-3 Development (spec-of-record:
`docs/research/ORGANISM-PROGRAM-PLAN.md`).

**Embedded context — the existing code you are extending (EXTEND, do not
rewrite):**

- `scripts/wave_kpi.py` — already owns the canonical event reader
  `read_events(path=EVENTS_LOG)` (JSONL → `list[dict]`, `[]` when the file is
  absent) and `busy_fraction_from_events(events)` (T1). It pairs
  `run_start`/`run_end` events by `run_id` and returns `None` when there are no
  paired runs (inert-by-design). Constants: `EVENTS_LOG =
  "board/.events.jsonl"`, `LIVE_LOG = "board/.wave-log"`. Make this module's
  `read_events` the ONE reader; T1 must derive from spans emitted by DAS-1455.
- `scripts/metrics_lib.py` — T2–T6 + anti-gaming (R-9) + T1b. It already
  `import wave_kpi` and calls `wave_kpi.parse` / consumes the event store. Every
  function here returns `None` when there is no live data (`idle_wave_rates`,
  `concurrency_stats`, `model_mix`, `recovery_reliability`,
  `review_efficiency`, `gaming_violations`, `t1b_high_impact`). Point its
  event-derived functions (`run_intervals`, `concurrency_stats`, `model_mix`,
  `recovery_reliability`, `review_efficiency`, `gaming_violations`,
  `t1b_high_impact`) at `wave_kpi.read_events` so there is a single reader; keep
  every inert-when-empty guard intact.
- `scripts/check_spans.py` — **does not exist yet; this ticket creates it.** A
  new validator that reads the same event store via `wave_kpi.read_events` and
  asserts that **100% of dispatches in a run produce a well-formed span**: every
  dispatched ticket has a matching `run_start` **and** `run_end` paired by
  `run_id`, each carrying the required fields (`run_id`, `ticket_id`, `model`,
  `created_at` ISO-8601). It must be inert (exit 0, "no events") when the store
  is absent/empty, and fail (non-zero) only when live events exist and a
  dispatch is missing/malformed.

**Extend-vs-new posture.** EXTEND `wave_kpi.py` and `metrics_lib.py` in place —
route all readers through the existing `wave_kpi.read_events`; do NOT add a
second parser or duplicate the `run_id` pairing logic. CREATE exactly one new
file, `scripts/check_spans.py`. Do not touch `board/.events.jsonl` schema owned
by DAS-1455 beyond consuming it.

**Cost/token reconciliation seam.** The cost-ledger lands in slice 2, so
cost/token sum fields may be absent today. Leave the seam: where a span carries
token/cost fields, `check_spans.py` (or a helper) must reconcile the per-run
token sums against the span-level sums and pass trivially (inert) when the
fields are absent — never fabricate a number.

**Consumes:** `span-builder`, `dispatch-emitter` (DAS-1455).

## Acceptance criteria

- [x] `wave_kpi.py` (T1) and the `metrics_lib.py` T2–T7 validators all derive
      from spans via the single shared `wave_kpi.read_events` source — no reader
      keeps a private/divergent run reconstruction.
- [x] New `scripts/check_spans.py` asserts 100% of dispatches in a run produce
      well-formed spans (matching paired `run_start`/`run_end` by `run_id` with
      required fields); exits non-zero on any missing/malformed dispatch when
      live events exist.
- [x] Token sums (once present) reconcile with span sums; the reconciliation
      passes inertly when token/cost fields are absent (cost-ledger is slice-2).
- [x] `python3 scripts/diagnostics.py` stays 100/100.
- [x] All validators (`wave_kpi`, `metrics_lib`, `check_spans`) remain
      inert-by-design — return `None`/exit 0 with a clear "no events" message —
      when the event store is absent or empty.

## Log

### 2026-07-03 — CEO
Created from ORGANISM program-plan decomposition (/daslab-plan). Spec-of-record: docs/research/ORGANISM-PROGRAM-PLAN.md.

### 2026-07-03 — Backend Engineer 1

GATE-3 implementation complete. Branch `feat/das-1456-recompute-spans`, commit bf4e736.

**Single-reader audit**: Confirmed all T1–T7 check scripts already call `wave_kpi.read_events`
as the one JSONL reader before passing events to `metrics_lib` functions. No private divergent
reader existed; the single-reader invariant was intact and is now explicitly documented.

**New file — `scripts/check_spans.py`**:
- Reads events via `wave_kpi.read_events` (single source of truth).
- Check 1 (coverage): every `run_start` run_id has a matching `span` event.
- Check 2 (validity): every `span` passes `dgox.events.validate_span` — all required
  OTel-GenAI fields, `trace_id == ticket_id`, `duration_ms == end - start`, `cached`
  consistent with `cached_input_tokens`.
- Check 3 (reconciliation seam): where `run_end.token_total` is present, verifies
  it equals sum of span `input_tokens + output_tokens` for that `run_id`. Currently
  inert (no `token_total` on `run_end` until slice-2 cost-ledger).
- Inert (exit 0, "no events") on absent/empty store.
- Shadow-test exclusion: `tests/test_dgox_phase1_shadow.py` updated to include
  `check_spans.py` in `_SPAN_VALIDATORS` (span validator using `validate_span`, not
  a dispatch-decision script — Phase-1 shadow rule intent preserved).

**New file — `tests/test_check_spans.py`**: 14 tests covering inert paths, full
coverage, partial missing span (exit 1), malformed span (exit 1), duration mismatch
(exit 1), cached flag inconsistency (exit 1), token reconciliation (inert + matching
pass + mismatch fail), and single-reader invariant.

**Reconciliation proof**: synthetic 3-dispatch wave emitted via `dispatch_emitter.emit_wave`
produces 9 events (`[run_start, run_end, span] × 3`); `check_spans.py` reports
"3 dispatch(es), 3 span(s) — all well-formed, coverage 100%", exit 0. Token
reconciliation is inert (no `token_total` on `run_end` events today).

**Full suite**: 1007 passed / 0 failed / 1 skipped; `diagnostics.py` 100/100;
`board_lint.py` 0 violations; `ruff check scripts tests` clean.

### 2026-07-03 — Orchestrator (/daslab-cycle collect)
Done via local-only done-gate: full suite 1020 pass + validators green + merge verification. Confirmed T1-T7 use single wave_kpi.read_events reader; added check_spans.py (coverage/validity/reconciliation, inert-by-design) + 14 tests.
