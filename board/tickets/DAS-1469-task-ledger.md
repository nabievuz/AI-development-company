---
id: DAS-1469
title: Task-ledger per run (facts and plan)
status: done
assignee: cpo
author: ceo
dept: engineering
priority: p1
parent: DAS-1463
goal: organism-ws2-loom
zone: runs-ledger
created: 2026-07-03
updated: 2026-07-03
---

## Description

**What.** Give every supervised run a durable, human-readable **task-ledger** —
`board/runs/<run_id>/task-ledger.md` — that captures, per run, the two things a
resumed or audited run needs but the checkpoint chain does not hold: (1) the
**facts** the wave is operating on, structured as *given / known / to-look-up /
educated-guesses*, and (2) the **plan** (the wave's ordered work). The ledger is
regenerated on **replan** so it always reflects the current understanding, not a
stale snapshot.

**Why.** This is the GATE-3 outer-loop deliverable (P7) of ORGANISM WS2 "LOOM".
The run-model from WS1 (ADR-0023, DAS-1443/1444) already durably records *what
happened* — event log, wave checkpoints, per-ticket completions, tamper-evident
ledger hashes. What it does NOT record is *what the run believed and intended*:
the working facts and the plan they justify. The task-ledger closes that gap so a
resumed run (or a human auditor) can read, in one file, the epistemic state the
wave planned from — and see how it changed when the plan was revised. It is the
producer for DAS-1470 (the downstream consumer of the ledger).

**Embedded context (spec-of-record + how it fits).**
- Spec-of-record: `docs/research/ORGANISM-PROGRAM-PLAN.md` (WS2 LOOM, P7 outer
  loop; GATE-3).
- Run object + on-disk layout: `docs/adr/0023-run-model.md` — `run_id` is a
  ULID (§1); each run owns `board/runs/<run_id>/` (§2) holding `manifest.json`
  (the immutable wave PLAN), `wave-NNN.checkpoint.json` (delta checkpoints), and
  `run-summary.md`. The task-ledger is a **new sibling artifact** in that same
  directory. Per §5, the entire `board/runs/<run_id>/` tree is **gitignored
  runtime state** EXCEPT retained summaries — the task-ledger is runtime state
  and stays gitignored (the existing `.gitignore` rule `board/runs/` +
  `!board/runs/*/run-summary.md` already covers it; do NOT un-ignore the ledger).
- The `run_id`, `board/runs/<run_id>/` directory, ULID generator
  (`generate_ulid()`), and the run-dir conventions ALL come from
  `scripts/pulse_checkpoint.py` (DAS-1444). REUSE them — do not fork a second
  run-dir scheme or a second ULID source.

**Extend-vs-new.** EXTEND the WS1 run-model, do NOT fork it. Reuse
`pulse_checkpoint.py`'s root-resolution (`_resolve_root`, `DASLAB_ROOT` env →
git → relative fallback), its `DEFAULT_RUNS_DIR` (`board/runs/`) constant, its
`generate_ulid()`, and the `created_at`-is-always-an-argument discipline
(injectable for tests, never generated inside a pure helper). The new
`scripts/task_ledger.py` helper is a **new file** (a distinct concern from
checkpoint/completion writing), but it imports and reuses the shared run-dir
conventions rather than re-deriving them. The `/daslab-cycle` wiring (writing the
ledger at wave-open and regenerating on replan) is a follow-up wiring change,
gated on the same `organism_emit` feature flag as the rest of the run-model —
this ticket ships the helper + tests; the SKILL wiring lands with the consumer.

**Key files (paths).**
- CREATE `scripts/task_ledger.py` — build / update (regenerate) / read helpers
  for `board/runs/<run_id>/task-ledger.md`.
- CREATE `tests/test_task_ledger.py` — unit tests (build, replan regeneration of
  both facts and plan, read round-trip, injectable `created_at`, gitignore
  posture).
- REUSE `scripts/pulse_checkpoint.py` — `_resolve_root`, `DEFAULT_RUNS_DIR`,
  `generate_ulid()`, run-dir conventions (do NOT duplicate).
- REFERENCE `docs/adr/0023-run-model.md` (§2 layout, §5 gitignore/retention),
  `docs/research/ORGANISM-PROGRAM-PLAN.md` (WS2 LOOM / P7).
- (Follow-up, not this ticket) `.claude/skills/daslab-cycle/SKILL.md` — where the
  ledger write/regenerate is wired into the wave, feature-gated on
  `organism_emit`.

**Scope (GATE-3, P7 outer loop).** Build the task-ledger: per run write
`board/runs/<run_id>/task-ledger.md` capturing facts (given / known / to-look-up
/ educated-guesses) + the plan, regenerated on replan (a facts-update and a
plan-update path). Add the `scripts/task_ledger.py` helper with build / update /
read + tests. Reuse the run-model (`board/runs/<run_id>/` from DAS-1444).
`board/runs/` stays gitignored except retained summaries.

## Acceptance criteria

- [x] `board/runs/<run_id>/task-ledger.md` is written per run, capturing **facts**
      (given / known / to-look-up / educated-guesses) **and** the **plan**.
- [x] The ledger is **regenerated on replan** — both a facts-update path and a
      plan-update path produce a refreshed ledger reflecting the current state
      (not appended stale sections).
- [x] `scripts/task_ledger.py` helper exists with build / update / read
      functions, reusing `pulse_checkpoint.py`'s run-dir conventions,
      `DEFAULT_RUNS_DIR`, and `generate_ulid()` (no forked run-dir scheme, no new
      dependency).
- [x] `created_at` is a caller-supplied argument (injectable for tests), never
      generated inside a pure helper — matches the WS1 discipline.
- [x] `tests/test_task_ledger.py` covers build, replan regeneration (facts +
      plan), and read round-trip.
- [x] The task-ledger stays **gitignored** under `board/runs/` (only
      `run-summary.md` is retained) — the existing `.gitignore` rule already
      covers it; no un-ignore is added.
- [x] Full test suite: 0 failed. Diagnostics: 100/100.
- [x] Produces the task-ledger artifact consumed by DAS-1470.

## Log

### 2026-07-03 — CEO
Created from ORGANISM WS2 LOOM decomposition (/daslab-plan). Spec-of-record: docs/research/ORGANISM-PROGRAM-PLAN.md.
To write precise criteria + paths, READ: scripts/pulse_checkpoint.py, docs/adr/0023-run-model.md, .claude/skills/daslab-cycle/SKILL.md.
Scope + acceptance: GATE-3 (P7 outer loop). Build the task-ledger: per run write board/runs/<run_id>/task-ledger.md capturing facts (given / known / to-look-up / educated-guesses) + the plan, regenerated on replan. Add a scripts/ helper (task_ledger.py) with build/update/read + tests. Reuse the run-model (board/runs/<run_id>/ from DAS-1444). board/runs/ stays gitignored except retained summaries.
Acceptance: task-ledger.md written per run with facts + plan; regenerated on replan (facts-update + plan-update); helper + tests; full suite 0 failed, diagnostics 100/100.
Produces: task-ledger (consumed by DAS-1470).
Constraints: org-engine, NO project: field (board_lint R9).

### 2026-07-03 — Senior Product Manager
Built the P7 outer-loop task-ledger. Shipped the helper + tests; SKILL wiring is the deliberate follow-up (lands with the DAS-1470 consumer, gated on `organism_emit` — per the ticket's Extend-vs-new note).

**Created `scripts/task_ledger.py`** — per-run `board/runs/<run_id>/task-ledger.md` writer. Public API:
- `Facts` dataclass — four epistemic buckets: `given` / `known` / `to_look_up` / `educated_guesses` (build/update also accept a plain dict of the buckets).
- `build_task_ledger(*, run_id, facts, plan, created_at, goal=None, wave=None, runs_dir=None) -> Path` — writes the initial ledger; `revision=1`; `created_at == updated_at`.
- `update_task_ledger(*, run_id, created_at, facts=None, plan=None, goal=None, wave=None, runs_dir=None) -> Path` — **regenerates on replan** (replace, never append): reads the existing ledger, bumps `revision`, preserves the original `created_at`, sets `updated_at=created_at` (the regen timestamp). Facts-only replan carries the plan forward; plan-only replan carries facts forward; omitted `goal`/`wave` carry forward.
- `read_task_ledger(run_id, runs_dir=None) -> dict` — round-trip parse (facts→`Facts`, plan→ordered `list[str]`, metadata); raises `FileNotFoundError` when absent.
- `render_task_ledger(...) -> str` (pure, no I/O) and `ledger_path(run_id, runs_dir=None) -> Path` helpers.

**Reuse (EXTEND, not fork):** binds `DEFAULT_RUNS_DIR` and `generate_ulid` directly from `pulse_checkpoint` (re-exported, single source of truth) — no second run-dir scheme, no second ULID source, no new dependency, no `dgox` import / event emission (ledger is a standalone markdown artifact, so ADR-0025 shadow rule does not apply). `created_at` is always a caller-supplied argument (a source-level test asserts the module never calls `datetime.now`/`utcnow`/`time.time`).

**Gitignore posture:** task-ledger.md is NOT `run-summary.md`, so the existing `.gitignore` rule (`board/runs/**` + negations) already ignores it; no `.gitignore` change. Verified with a `git check-ignore` test.

**Created `tests/test_task_ledger.py`** — 22 tests: reuse-of-run-model, build (4 fact buckets + ordered plan, revision=1, dict facts, run-dir autocreate, empty-bucket placeholder), read round-trip (+ render/parse inverse, missing→raise), replan regeneration (facts-update path, plan-update path, replace-not-append, revision bump + created_at preserved/updated_at advanced, update-missing→raise), injectable timestamp, gitignore.

**Verify (FULL, green):** `python3 -m pytest -q` → 1105 passed, 1 skipped (new module 22/22); `diagnostics.py` → 100/100; `board_lint.py` → 0 violations (32 tickets); `ruff check scripts tests` → clean. Committed LOCAL-only on `feat/das-1469-task-ledger` (no push, per strict local-only directive).

Status → `in_review`, assignee → cpo (my manager per ROUTING; never self-review). Routing note: DAS-1470 is the downstream consumer of this artifact; the `/daslab-cycle` SKILL wiring (write at wave-open, regenerate on replan, gated on `organism_emit`) is the follow-up that lands with it.

### 2026-07-03 — Orchestrator (/daslab-cycle collect)
Done via local-only done-gate: full suite 1105 pass, task_ledger.py + 22 tests, reuses run-model, gitignored. 
