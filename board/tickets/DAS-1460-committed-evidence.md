---
id: DAS-1460
title: Committed evidence — snapshot KPIs and spans to tracked metrics/evidence (P13)
status: done
assignee: cto
author: ceo
dept: engineering
priority: p1
parent: DAS-1457
goal: organism-ws3-slice2
zone: metrics-evidence
created: 2026-07-03
updated: 2026-07-03
---

## Description

### What & why

DasLab's KPI gates (T1–T6 + anti-gaming R-9) all read the append-only DGO-X
event store at `board/.events.jsonl`. That store is **gitignored runtime state**
— it exists only on the machine that ran the wave and is never committed. This
means the gates rest on evidence that cannot be audited from the git history: a
reviewer on a fresh clone has *nothing* to verify a claimed KPI against, and
runtime state can be silently regenerated or lost.

This ticket (P13, "committed evidence") builds the durable, git-auditable proof
the gates rest on. For each run it snapshots that run's `wave_kpi` summary plus
its span aggregates into a **TRACKED** (committed, NOT gitignored) artifact at
`metrics/evidence/<run_id>.json`. The snapshot is small and **redacted** — no
secrets, no PII, no free-form prompt/output text (redaction per the spirit of
ADR-0012: keep only structural/aggregate metric fields, never payloads). This
gives a permanent, reviewable record separate from the ephemeral event store.

The gate teeth: `scripts/check_metric_gaming.py` is extended to **require** a
committed evidence file for every run that has counted completions. A run whose
completions are counted toward the KPIs but that has **no committed evidence
snapshot** FAILS the anti-gaming / metric-gaming gate (a Goodhart defence: you
cannot count work toward the metrics without leaving durable, committed proof).

### Embedded context — how the pieces fit

- **Event store (runtime, gitignored):** `board/.events.jsonl`. Produced by
  `scripts/dispatch_emitter.py` (paired `run_start`/`run_end` + `span` events,
  joined by `run_id`). Read by `scripts/wave_kpi.py` and `scripts/metrics_lib.py`.
- **`scripts/wave_kpi.py`** — `read_events(path)` reads the JSONL store;
  `busy_fraction_from_events(events)` returns `(fraction_or_None, stats)` where
  `stats = {events, runs_started, runs_completed, model_mix}`. The reader pairs
  `run_start`/`run_end` by `run_id` and counts `model` once per `run_start`.
  Every reader returns `None`/inert when there is no live data.
- **`scripts/metrics_lib.py`** — T2–T6 + anti-gaming. Relevant here:
  `run_intervals(events)` (paired `[run_start, run_end]` intervals),
  `gaming_violations(events)` (R-9: a completion counts only with
  `merged_pr` + green `ci_status` + `t7_pass`; returns
  `{completions, violations}` or `None` when there are no completions),
  `_is_completion_event(ev)`, and `_unit_key(ev)` (uses `run_id`/`ticket_id`).
- **`scripts/check_metric_gaming.py`** — the anti-gaming gate CLI. Reads the
  store via `wave_kpi.read_events`, calls `metrics_lib.gaming_violations`, and
  exits `0` (no gaming OR unmeasured/inert), `1` (counted busywork found), or
  `2` (usage error). It is currently **inert (exit 0)** when there are no
  completions. It takes `--events board/.events.jsonl` and resolves `ROOT` from
  `scripts/_paths.py`.
- **`scripts/dispatch_emitter.py`** — the event PRODUCER. `DispatchRecord`
  carries `run_id`, `ticket_id`, `model`, `outcome`, `merged_pr`, `ci_status`,
  `t7_pass`, `t7_score`, `start`/`end`, etc. This is the shape the evidence
  snapshot summarizes per `run_id`.

### Extend-vs-new posture (REUSE, do not fork)

- **New file:** `scripts/snapshot_evidence.py` — the helper that reads the event
  store and writes `metrics/evidence/<run_id>.json`. It must **REUSE**
  `wave_kpi.read_events`, `wave_kpi.busy_fraction_from_events` /
  `metrics_lib.run_intervals`, and the existing completion/evidence field names
  from `metrics_lib` (`merged_pr`, `ci_status`, `t7_pass`, `t7_score`,
  `outcome`, `model`). Do NOT re-implement event parsing or re-derive field
  names — import and call the existing functions.
- **Extend (do not rewrite):** `scripts/check_metric_gaming.py` — add the
  evidence-presence requirement alongside the existing `gaming_violations`
  check. Keep the existing exit-code contract and the inert-when-no-completions
  behaviour. Do NOT modify `wave_kpi.py`, `metrics_lib.py`, or
  `dispatch_emitter.py`.
- **Inert-by-design:** when the event store is absent/empty (no runs), the
  helper writes nothing and the gate stays inert (exit 0). Never fabricate an
  evidence file or a KPI number.

### Key existing files (paths)

- `scripts/wave_kpi.py`
- `scripts/metrics_lib.py`
- `scripts/check_metric_gaming.py`
- `scripts/dispatch_emitter.py`
- `scripts/dgox/events.py` (typed builders / `EventStore`)
- `scripts/_paths.py` (`ROOT`)
- `board/.events.jsonl` (gitignored runtime event store)
- `.gitignore` (must NOT ignore `metrics/evidence/`)
- `docs/research/ORGANISM-PROGRAM-PLAN.md` (spec-of-record)

### AADL stage

GATE-3/4 (Development / Testing). Close the stage in the project stage-board
after the acceptance checklist is green.

## Acceptance criteria

- [ ] A new `scripts/snapshot_evidence.py` reads the event store (via
      `wave_kpi.read_events`) and, for each run with counted completions, writes
      a **TRACKED** (committed, NOT gitignored) snapshot to
      `metrics/evidence/<run_id>.json` that is small and **redacted** — only
      aggregate/structural fields (e.g. `run_id`, ticket ids, `model`,
      `outcome`, `merged_pr`, `ci_status`, `t7_pass`, `t7_score`, span/duration
      aggregates, `wave_kpi` summary stats). No secrets, no PII, no raw
      prompt/output payloads (redaction per ADR-0012 spirit).
- [ ] The snapshot REUSES existing readers/field names from `wave_kpi.py` /
      `metrics_lib.py` (no re-implemented event parsing, no re-derived field
      names); `wave_kpi.py`, `metrics_lib.py`, and `dispatch_emitter.py` are
      NOT modified.
- [ ] `scripts/check_metric_gaming.py` is extended to **require** an evidence
      file for a run's counted completions: a run that has counted completions
      but **no** committed `metrics/evidence/<run_id>.json` FAILS the gate
      (non-zero exit) with a clear message naming the run id(s). The existing
      `gaming_violations` (merged_pr + green CI + T7) check and exit-code
      contract are preserved.
- [ ] Inert when no runs exist: absent/empty event store ⇒ no evidence file is
      written and the gate stays inert (exit 0); no fabricated file or KPI.
- [ ] A synthetic run (fixture events → snapshot helper) produces a
      well-formed, committed evidence file whose contents match the run's event
      data; a test asserts the file is valid JSON, redacted (no secret/PII/
      payload fields), and keyed by `run_id`.
- [ ] `check_metric_gaming` behaviour is tested: (a) run WITH evidence file
      passes; (b) counted-completion run WITHOUT evidence file fails; (c) no
      completions ⇒ inert exit 0.
- [ ] `.gitignore` does NOT ignore `metrics/evidence/` — the directory and its
      snapshots are committed (verify a snapshot is tracked, not ignored).
- [ ] Tests live under the repo's existing test tree and pass.
- [ ] `python3 scripts/diagnostics.py` (or the repo's diagnostics entrypoint)
      reports 100/100.

## Log

### 2026-07-03 — CEO
Created from ORGANISM WS3 slice-2 decomposition (/daslab-plan). Spec-of-record: docs/research/ORGANISM-PROGRAM-PLAN.md.

### 2026-07-03 — QA Lead
Built the committed-evidence mechanism (P13). Branch `feat/das-1460-committed-evidence`, local-only.

- **New `scripts/snapshot_evidence.py`** — reads the DGO-X store via
  `wave_kpi.read_events` and, for each completed run, writes a TRACKED, REDACTED
  snapshot to `metrics/evidence/<run_id>.json`. REUSES `wave_kpi.busy_fraction_from_events`,
  `metrics_lib.run_intervals`, and the R-9 evidence vocabulary (`GREEN_CI` /
  `_is_true_flag` / `_is_completion_event`) — no re-implemented parsing, no
  re-derived field names. Does NOT import `dgox.*` (reader/summarizer, not a
  producer → Phase-1 shadow rule + `test_dgox_phase1_shadow` P1 stay intact).
  Redaction: `merged_pr`/`t7_pass` reduced to booleans (presence only — the raw
  PR URL body never enters git history); only structural/aggregate fields
  (run_id, ticket ids, model, outcome, ci_status, t7_score, span/duration
  aggregates, wave_kpi summary stats) are written. Inert when the store is
  absent/empty (writes nothing, fabricates no KPI).
- **Extended `scripts/check_metric_gaming.py`** — added a committed-evidence
  requirement (`--evidence-dir`, default `metrics/evidence`): a run whose
  completion is COUNTED per R-9 (merged_pr + green CI + T7) but has no committed
  `metrics/evidence/<run_id>.json` FAILS the gate (exit 1) naming the run id(s).
  The existing `gaming_violations` R-9 check, T1b reporting, and exit-code
  contract (0 inert/clean, 1 gamed-or-missing-evidence, 2 usage) are preserved.
  `wave_kpi.py` / `metrics_lib.py` / `dispatch_emitter.py` NOT modified.
- **`.gitignore`** already does NOT ignore `metrics/evidence/`; added a tracked
  `metrics/evidence/.gitkeep` so the committed dir exists on a fresh clone.
  Verified via `git check-ignore` (a snapshot path is NOT ignored) — asserted in
  a test.
- **Tests** `tests/test_snapshot_evidence.py` (12): snapshot is valid JSON,
  redacted (no PR URL / payload keys), keyed by run_id, contents match event
  data; inert on empty store; gate (a) passes WITH evidence, (b) fails WITHOUT
  for a counted run, (c) inert with no completions; R-9 gaming still fails;
  metrics/evidence committed-not-ignored.

VERIFY (all green, local): `python3 -m pytest -q` → 1032 passed, 1 skipped;
`diagnostics.py` 100/100; `board_lint.py` 0 violations; `check_metric_gaming.py`
inert exit 0 (no runs); `ruff check scripts tests` clean.

Acceptance criteria all satisfied. → `in_review`, assignee `cto` (ROUTING: QA
Lead's manager; no self-review). No push/PR (local-only per run scope).

### 2026-07-03 — CTO (review)

**Verdict: PASS → done.** Blocking review of the anti-gaming (R-9) gate change,
merged locally at 409c4aa. Reviewed on MAIN (no self-review — QA Lead built it).

Anti-gaming-safety items verified:

- **R-9 not weakened.** `check_metric_gaming.py` runs the existing
  `gaming_violations` (merged_pr + green CI + T7) check FIRST and returns exit 1
  on any violation; the new committed-evidence check only runs after R-9 is
  clean. `test_gate_gaming_violation_still_fails` (red CI) confirms R-9 still
  bites regardless of evidence presence.
- **Inert-by-design on the empty store.** With no completions
  `gaming_violations` returns `None` → gate prints "unmeasured" and exits 0
  before the evidence check is ever reached. Live run confirmed: exit 0.
- **Backward-compatible / correctly scoped.** The evidence teeth key on
  `counted_run_ids` = R-9-clean completions that CARRY a `run_id`; completions
  without a `run_id` cannot map to a snapshot and are out of scope (legacy
  fixtures stay green). A gamed completion is not counted, so needs no evidence
  (`test_counted_run_ids_excludes_gamed_and_run_id_less`).
- **Redaction (P13).** `snapshot_evidence.build_run_evidence` reduces
  `merged_pr`/`t7_pass` to booleans (presence only) and emits only
  structural/aggregate fields — no PR URL body, no prompt/output payload.
  `test_snapshot_is_redacted` asserts the raw PR URL is absent and no
  secret/PII/payload keys appear.
- **ADR-0025 shadow rule intact.** `snapshot_evidence.py` imports only
  `metrics_lib` / `wave_kpi` / `_paths` (the only `dgox` token is in its
  docstring) — reader/summarizer, not a producer. `test_dgox_phase1_shadow`
  (17 tests) still green.
- **Committed, not gitignored.** `git check-ignore` on a snapshot path exits 1
  (not ignored); `metrics/evidence/.gitkeep` is tracked (`git ls-files`).

Validator results (local): `diagnostics.py` 100/100;
`check_metric_gaming.py` inert exit 0; `pytest tests/test_snapshot_evidence.py`
12 passed; targeted shadow/gaming/evidence suite 53 passed, 1 skipped. Sign-off
recorded local-only — no push/PR per run scope (origin is PUBLIC; Founder
local-only mandate).
