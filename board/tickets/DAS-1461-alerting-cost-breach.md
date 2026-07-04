---
id: DAS-1461
title: Alerting cost-breach and per-run budget governor
status: done
assignee: sre-lead
author: ceo
dept: engineering
priority: p1
parent: DAS-1457
goal: organism-ws3-slice2
depends_on: [DAS-1459]
zone: scripts/alerting
created: 2026-07-03
updated: 2026-07-03
---

## Description

**What.** Teach the proactive alerter to fire a **cost-breach** alert when the
cost-ledger totals cross the budget thresholds, and ship a reusable **per-run
budget governor** library that classifies current spend as `ok` / `warn` /
`breach`. The governor is a pure, callable function — a later WS4 HEARTBEAT
ticket will consume it to gate live spend. This ticket does **not** wire the
governor into any live loop.

**Why.** Right now `scripts/alerting.py` watches throughput/quality/memory
signals (T1 busy fraction, T7 regression, break-glass, QONUN-5 never-auto
violations, memory health) but is blind to cost. As the ORGANISM program moves
toward autonomous waves, an unbounded run can burn the budget with no proactive
signal. This slice closes the cost-visibility gap: budgets defined once
(`config/budgets.yaml`, from DAS-1459) become an actively enforced alert, and
the shared governor gives WS4 a single source of truth for the spend gate.

**AADL stage:** GATE-3 (Development).

**Depends on DAS-1459** — that ticket lands `scripts/cost_ledger.py` (the
per-run/per-day cost totals) and `config/budgets.yaml` (the per-run and per-day
budget thresholds). Do not start the runtime-integration parts until those exist;
if 1459 is not yet merged, the ledger reader and budgets schema described below
are your contract with it. Coordinate on the exact function/key names 1459
exposes (e.g. a `totals()` / `read_totals()` accessor returning per-run and
per-day cost) and adapt the code below to match rather than inventing a parallel
reader.

**Extend, do NOT rewrite.** All work extends `scripts/alerting.py` in place. The
existing pure-evaluation architecture is the pattern to follow:
- `evaluate_alerts(readings, thresholds)` is a **pure** function that turns a
  `readings` dict into a severity-sorted alert list via the local `add(...)`
  helper. Add cost-breach alerts here (or in a small pure helper it calls) — do
  not add I/O to this function.
- `gather_readings(...)` is where live data is pulled and `None`/`False`/`0` is
  used when data is absent (inert-until-live). Add the cost-ledger read here,
  degrading to inert when the ledger/budgets are missing.
- `filter_quiet(alerts)` (Quiet Mode = anomalies only) and the `break_glass`
  integration must keep working exactly as-is.

**Key existing files (paths):**
- `scripts/alerting.py` — the alerter to extend (evaluate_alerts / gather_readings /
  filter_quiet / main; loads YAML via `_load_yaml`, JSONL via `_load_jsonl`).
- `scripts/cost_ledger.py` — cost totals source (**created by DAS-1459**; import it
  the way alerting already imports sibling libs, e.g. `import wave_kpi`,
  `import break_glass`, `import memory_lib`).
- `config/budgets.yaml` — per-run and per-day budget thresholds (**created by
  DAS-1459**). Read it with the existing `_load_yaml` helper; degrade to inert
  (no cost alert) when absent or empty.
- `config/alert_thresholds.yaml` — existing threshold SSOT (version 1, under a
  top-level `thresholds:` key). Cost thresholds live in `budgets.yaml` (owned by
  1459), not here; do not duplicate them into alert_thresholds.yaml.
- `scripts/break_glass.py`, `scripts/memory_lib.py`, `scripts/wave_kpi.py` —
  siblings already imported by alerting; the import/style precedent to mirror.
- Test dir: place tests next to the repo's existing alerting tests (follow the
  established `tests/` layout and naming, e.g. `tests/test_alerting*.py`).

**Governor contract (this ticket delivers the library, not its wiring):**
- A pure function, e.g. `budget_governor(totals: dict, budgets: dict) -> dict`
  (or `-> str` status plus detail) living in `scripts/alerting.py`, returning a
  verdict of `ok` / `warn` / `breach`:
  - `ok` — spend under the warn band.
  - `warn` — spend in the warn band (≥ a warn ratio of budget, e.g. crossing a
    configurable fraction such as 0.8× the limit) but under the hard limit.
  - `breach` — per-run OR per-day total ≥ its budget limit.
- Evaluate **both** per-run and per-day; the overall verdict is the most severe
  of the two. Missing budget or missing total for a dimension → that dimension
  is inert (does not fabricate a breach).
- The cost-breach **alert** in `evaluate_alerts` is derived from the governor
  verdict: `warn` → `warning` severity, `breach` → `critical` severity, `ok` →
  no alert. Give it a clear `metric` label (e.g. `COST` or `BUDGET`) and a
  message naming which dimension breached and by how much.
- Do **NOT** import the governor into any live wave/heartbeat loop, and do not
  add a daemon or scheduler — it is a callable library only. WS4 owns the wiring.

## Acceptance criteria

- [ ] `scripts/alerting.py` fires a **cost-breach alert** when cost-ledger totals
      exceed the `config/budgets.yaml` thresholds — evaluated for **both**
      per-run and per-day dimensions.
- [ ] A **per-run budget governor** library function exists in
      `scripts/alerting.py` returning `ok` / `warn` / `breach` given ledger
      totals + budgets; it is **pure** (no I/O, no side effects) and is **not**
      wired into any live loop/daemon (WS4 will consume it later).
- [ ] Governor verdict maps to alert severity: `warn` → `warning`, `breach` →
      `critical`, `ok` → no cost alert; the alert message names the breaching
      dimension (per-run vs per-day) and the amount over budget.
- [ ] Cost signals degrade to **inert** (no cost alert, no crash) when
      `scripts/cost_ledger.py` data or `config/budgets.yaml` is absent/empty —
      matching the existing "inert until live evidence exists" behavior.
- [ ] **Existing alerting behavior is unchanged**: T1 busy-fraction, memory
      health, T7 regression, QONUN-5 never-auto violations, break-glass alerts,
      Quiet Mode (`--quiet` = anomalies only), and `--fail-on-critical` exit
      code all behave exactly as before.
- [ ] **Tests** cover: cost-breach fires at/over per-run limit; cost-breach
      fires at/over per-day limit; governor returns `ok` / `warn` / `breach`
      across bands; inert degradation when ledger/budgets missing; a regression
      assertion that the pre-existing alerts and Quiet Mode still work.
- [ ] `python3 scripts/diagnostics.py` (or the repo's diagnostics entry) reports
      **100/100**, and **ruff** is clean on changed files.

## Log

### 2026-07-03 — CEO
Created from ORGANISM WS3 slice-2 decomposition (/daslab-plan). Spec-of-record: docs/research/ORGANISM-PROGRAM-PLAN.md.

### 2026-07-03 — SRE Engineer
Implemented and committed on branch `feat/das-1461-alerting` (local only, no push per Founder policy).

**Cost-breach wiring:**
- `gather_readings()` imports `cost.cost_ledger.aggregate_spans` (guarded `try/except ImportError`); on success pulls `per_run_cost_usd` (max cost across `by_run` groups) and `per_day_cost_usd` (`raw_estimated_cost_usd` as a total-spend proxy). Both degrade to `None` when the ledger is absent, the event store is empty, or any exception is raised — matching the existing inert-until-live pattern.
- `evaluate_alerts()` gained a `budgets: dict | None = None` keyword arg (backward-compatible default). When non-empty, it calls `budget_governor()` and maps `warn→warning`, `breach→critical`, routing a single `COST` alert with dimension names and over-by amounts in the message.
- `main()` loads `config/budgets.yaml` via a new `--budgets` flag (default `ROOT/config/budgets.yaml`); passes it to both `gather_readings` (for ledger pricing) and `evaluate_alerts` (for cap evaluation). Absent file → `_load_yaml` returns `{}` → inert.

**Governor API (`budget_governor(totals, budgets) -> dict`):**
- Pure function — no I/O, no side effects.
- Evaluates `per_run_cost_usd` vs `caps.per_run.max_cost_usd` and `per_day_cost_usd` vs `caps.per_day.max_cost_usd` independently.
- Verdict per dimension: `breach` (≥ limit), `warn` (≥ 80% of limit, configurable via `budgets.warn_ratio`), `ok` (below warn band).
- Overall `status` = most severe of all evaluated dimensions. `details` list includes only non-ok dimensions.
- Missing total or missing limit for a dimension → that dimension is inert (no fabricated breach).

**Existing behaviour unchanged:** T1 busy-fraction, memory health, T7 regression, QONUN-5, break-glass, Quiet Mode (`filter_quiet`), and `--fail-on-critical` all work exactly as before. Tests confirm this.

**Full suite results:**
- `python3 -m pytest -q`: 1082 passed, 1 skipped, 0 failed
- `python3 scripts/diagnostics.py`: SCORE = 100/100
- `python3 scripts/board_lint.py`: 0 violations
- `python3 scripts/alerting.py`: exits 0, "Alerts: none — system nominal"
- `ruff check scripts/alerting.py tests/test_alerting_cost.py`: All checks passed

**Files changed:**
- `scripts/alerting.py` — extended (budget_governor + cost wiring)
- `tests/test_alerting_cost.py` — new (30 tests: governor bands, evaluate_alerts cost paths, inert degradation, regressions, CLI smoke)

Commit: `5d5eacd` on `feat/das-1461-alerting`. Handoff to sre-lead for review.

### 2026-07-03 — Orchestrator (/daslab-cycle collect)
Done via local-only done-gate: full suite 1082 pass + validators green; budget_governor is an inert library (WS4 consumes later), existing alerting unchanged. Local-only observed (no push).
