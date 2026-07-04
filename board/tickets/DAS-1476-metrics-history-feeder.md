---
id: DAS-1476
title: Metrics-history feeder for clean-day streak
status: done
assignee: backend-em
author: ceo
dept: engineering
priority: p1
parent: DAS-1472
goal: organism-ws4-heartbeat
zone: metrics-history
created: 2026-07-03
updated: 2026-07-03
---

## Description

GATE-3. Build the `board/.metrics-history.jsonl` **feeder**: the producer that
turns a run/window's real span+run events into the per-day rows
`loop_controller.py` reads to count consecutive clean days for GATE-6 promotion
eligibility.

**Why.** `scripts/loop_controller.py` is the self-optimization promotion
controller. It EVALUATES (never applies) whether the loop may climb one rung
(`shadow → measured → limited_live → full`) — and one blocker is `>= 7`
consecutive clean live days. It reads those days from
`board/.metrics-history.jsonl` via `_load_jsonl(...)` and counts the streak with
`clean_live_days(metrics_history, targets)`:

```python
def clean_live_days(metrics_history, targets):
    """Consecutive clean days at the END of the (oldest->newest) history."""
    streak = 0
    for day in reversed(metrics_history):
        if day_is_clean(day, targets):
            streak += 1
        else:
            break
    return streak
```

Today NOTHING writes that file — the controller always reads an empty list and
reports `0/7 clean day(s)` (never fabricates readiness). This ticket ships the
missing producer so real waves can accrue a genuine, evidence-backed streak.

**Exact schema the feeder must emit (this is load-bearing).** Each row is one
JSON object per line. `day_is_clean(day, targets)` (loop_controller.py:57-71)
requires these keys with these meanings, gated against `DEFAULT_TARGETS`
(`t1_min 0.60, t2_max 0.15, t3_min 6, t4_min 0.25, t5_min 0.99`):

- `t1` (float) — busy fraction; clean when `>= 0.60`
- `t2` (float) — idle-wave rate; clean when `<= 0.15`
- `t3` (number) — effective concurrency; clean when `>= 6`
- `t4` (float) — low-cost model share; clean when `>= 0.25`
- `t5` (float) — recovery reliability; clean when `>= 0.99`
- `t7_holds` (bool) — clean requires `True`

Recommended additional fields for provenance (loop_controller ignores extra
keys, so they are safe): `date` (`YYYY-MM-DD`) and a window bound. Any timestamp
the row carries MUST use the store's canonical format `YYYY-MM-DDTHH:MM:SSZ`
(the exact format `wave_kpi._parse_iso` / `metrics_lib._parse_iso` parse).
Rows MUST be appended **oldest → newest** — `clean_live_days` walks the list in
reverse and counts the trailing run, so newest-last is mandatory.

**Compute from REAL span/run events — never a hand-picked number.** Read the
DGO-X event store (`board/.events.jsonl`) and the wave log via the existing
readers and derive the T-values from them:

- `t1` ← `wave_kpi.busy_fraction_from_events(events)` (returns `None` when there
  are no paired runs / zero span — carry `None` through, do NOT coerce to 0).
- `t2` ← `metrics_lib.idle_wave_rates(waves)` (use `t2a_rate` — the idle/waste
  component; `t2b_blocked` is not waste).
- `t3` ← `metrics_lib.concurrency_stats(events)["median"]`.
- `t4` ← `metrics_lib.model_mix(events)["ratio"]`.
- `t5` ← `metrics_lib.recovery_reliability(events)["ratio"]`.
- `t7_holds` ← derive from evidence already in the store (e.g.
  `metrics_lib.gaming_violations` clean + `t1b_high_impact` / T7 pass flags); do
  not invent a T7 pass.

When a metric reader returns `None` (no live data), the day is NOT clean and the
feeder must reflect that honestly (emit the row with the missing metric absent /
below-target, or skip emission for that empty window) — it must NEVER fabricate
a passing value to inflate the streak. This mirrors the "inert, never faked"
contract in `metrics_lib` and `dispatch_emitter`.

**Extend, do NOT fork.** Import and REUSE `wave_kpi.py`, `metrics_lib.py`, and
(for reading the store) their existing readers; do not re-implement event
parsing, interval pairing, or percentile math. Do not modify `loop_controller.py`,
`wave_kpi.py`, or `metrics_lib.py` — match their contracts exactly. This ticket
is the read-side sibling of `dispatch_emitter.py` (the run-event producer):
`dispatch_emitter` writes `board/.events.jsonl`; this feeder consumes those
events and writes the per-day `board/.metrics-history.jsonl` rows.

**Runtime state, gitignored.** `board/.metrics-history.jsonl` is append-only
runtime state and MUST be gitignored (same class as `board/.events.jsonl` and
`board/.wave-log`) — never committed. Verify/extend the `.gitignore` entry.

### Key files + paths

- NEW: `scripts/metrics_history_feeder.py` (the feeder + a small CLI to append a
  window's row; pure core takes injected events/timestamps, no clock read in the
  core path — mirror `dispatch_emitter`'s injectable-timestamp design so it is
  deterministically unit-testable).
- NEW: `tests/test_metrics_history_feeder.py`.
- READ / REUSE: `scripts/loop_controller.py` (schema of record — the contract),
  `scripts/wave_kpi.py`, `scripts/metrics_lib.py`, `scripts/dispatch_emitter.py`.
- WRITE TARGET (runtime, gitignored): `board/.metrics-history.jsonl`.
- Spec-of-record: `docs/research/ORGANISM-PROGRAM-PLAN.md`.

## Acceptance criteria

- [x] Metrics-history feeder appends rows to `board/.metrics-history.jsonl` in
      `loop_controller`'s EXACT schema (`t1..t5`, `t7_holds`) and key names, in
      oldest→newest order.
- [x] Any timestamp in a row uses `YYYY-MM-DDTHH:MM:SSZ`.
- [x] T-values are computed from REAL span/run events via `wave_kpi` +
      `metrics_lib` (no hand-picked numbers); `None`/no-live-data windows never
      fabricate a passing metric.
- [x] `loop_controller.clean_live_days` computes the consecutive clean-day
      streak correctly against feeder-produced rows (test covers a clean
      trailing run, a break in the middle, and an all-empty history → 0).
- [x] `board/.metrics-history.jsonl` is gitignored; never committed.
- [x] `loop_controller.py` / `wave_kpi.py` / `metrics_lib.py` are unmodified.
- [x] Full suite 0 failed, diagnostics 100/100.

## Log

### 2026-07-03 — CEO
Created from ORGANISM WS4 HEARTBEAT decomposition (/daslab-plan). Spec-of-record: docs/research/ORGANISM-PROGRAM-PLAN.md.
READ for precision: scripts/loop_controller.py, scripts/wave_kpi.py, scripts/metrics_lib.py, scripts/dispatch_emitter.py.

### 2026-07-03 — Backend Engineer 1
Implemented the full feeder. Branch: feat/das-1476-metrics-history. Commit: 2f7161e.

Files created:
- scripts/metrics_history_feeder.py — pure-core feeder: compute_window_row (delegates
  T1→wave_kpi.busy_fraction_from_events, T2→metrics_lib.idle_wave_rates.t2a_rate,
  T3→metrics_lib.concurrency_stats.median, T4→metrics_lib.model_mix.ratio,
  T5→metrics_lib.recovery_reliability.ratio, T7_holds→metrics_lib.gaming_violations);
  filter_events_by_window / filter_waves_by_date / emit_all_days (oldest→newest);
  append_history_row (append-only); CLI with --date / --start / --end / --all.
  Zero clock reads in the pure core — injectable timestamps throughout (mirrors
  dispatch_emitter pattern). ADR-0025 operator-tempo reader: does NOT affect dispatch.
- tests/test_metrics_history_feeder.py — 43 tests covering: streak (clean trailing run,
  break in middle, all-empty → 0), T7_holds derivation, missing-metric non-fabrication,
  append-only behaviour, emit_all_days order, gitignore check, CLI smoke.
- .gitignore — added board/.metrics-history.jsonl entry.

Modified files: none (loop_controller.py / wave_kpi.py / metrics_lib.py untouched).

Verification: python3 -m pytest -q → 1281 passed 1 skipped 0 failed;
python3 scripts/diagnostics.py → 100/100; python3 scripts/board_lint.py → 0 violations;
ruff check scripts tests → All checks passed.

### 2026-07-03 — Orchestrator (/daslab-cycle collect)
Done via local-only done-gate: full suite green + validators. metrics_history_feeder.py: T1-T5+T7_holds window rows matching loop_controller schema (43 tests); loop_controller/wave_kpi/metrics_lib untouched; gitignored.
