---
id: DAS-1477
title: Run-workspaces scratch dir with GC on run close
status: done
assignee: backend-em
author: ceo
dept: engineering
priority: p1
parent: DAS-1472
goal: organism-ws4-heartbeat
zone: runs-workspace
created: 2026-07-03
updated: 2026-07-03
---

## Description

Autonomous runs currently have no dedicated scratch space, so intermediate
artifacts either leak into the repo working tree or are lost between steps.
This ticket (GATE-3, P16 of the ORGANISM WS4 HEARTBEAT program) gives each
autonomous run a private, garbage-collected scratch directory while retaining
only the durable run summary.

**What/why.** Each autonomous run gets `board/runs/<run_id>/workspace/` — a
scratch space for intermediate files during the run. On run close the workspace
is garbage-collected (deleted), but the final `run-summary.md` is retained. This
keeps the repo clean (scratch never persists) while preserving the auditable
record of what each run did.

**Extend vs new.** EXTEND, do not fork the run model. Reuse the DAS-1444
run-model layout (`board/runs/<run_id>/`) already established for runs.
`run-summary.md` continues to be the retained, non-scratch artifact of a run;
`workspace/` is a new sibling subdir that is scratch-only. Add a `scripts/`
helper that creates the workspace at run start and GCs it on run close (keeping
`run-summary.md`), plus tests. `board/runs/` must be gitignored EXCEPT retained
summaries.

**Key files + paths.**
- Spec-of-record: `docs/research/ORGANISM-PROGRAM-PLAN.md`
- Read for precision: `scripts/pulse_checkpoint.py`, `docs/adr/0023-run-model.md`
- Run-model reference: DAS-1444 (`board/runs/<run_id>/`)
- New/edited: `scripts/` helper (workspace create + gc-on-close), its tests,
  and the `.gitignore` rule scoping `board/runs/` (allow retained summaries).

Constraints: org-engine ticket — NO `project:` field. Scope stays inside the
engine (scripts/, tests, docs, gitignore).

## Acceptance criteria

- [x] `board/runs/<run_id>/workspace/` is created per run
- [x] GC on run close deletes the workspace but keeps `run-summary.md`
- [x] `board/runs/` is gitignored except retained summaries
- [x] `scripts/` helper + tests added
- [x] full test suite: 0 failed
- [x] diagnostics 100/100

## Log

### 2026-07-03 — CEO
Created from ORGANISM WS4 HEARTBEAT decomposition (/daslab-plan). Spec-of-record: docs/research/ORGANISM-PROGRAM-PLAN.md.
READ for precision: scripts/pulse_checkpoint.py, docs/adr/0023-run-model.md.
Scope+acceptance (expand; keep frontmatter exact): GATE-3 (P16). Each autonomous run gets board/runs/<run_id>/workspace/ (scratch, garbage-collected at run close; final summary retained). Reuse the DAS-1444 run-model (board/runs/<run_id>/). Add a scripts/ helper (create workspace, gc-on-close keeping run-summary.md) + tests. board/runs/ gitignored except retained summaries.
Acceptance: [ ] board/runs/<run_id>/workspace/ created per run; [ ] GC on close keeps run-summary.md; [ ] gitignored; [ ] helper + tests; [ ] full suite 0 failed, diagnostics 100/100.
Constraints: org-engine, NO project: field.

### 2026-07-03 — Backend Engineer 2
Implemented P16 run-workspaces:
- Created `scripts/run_workspace.py` — three-function public API:
  `workspace_path()`, `create_workspace()` (idempotent mkdir), `gc_workspace()`
  (shutil.rmtree of workspace/ only; leaves run-summary.md, manifest, checkpoints
  intact; returns True/False for deleted/not-present). Follows same self-locating
  root pattern as pulse_checkpoint.py (DASLAB_ROOT env → git rev-parse → fallback).
- Created `tests/test_run_workspace.py` — 24 tests covering workspace_path,
  create_workspace (idempotency, parent creation), gc_workspace (leave-summary,
  recursive delete, sibling-run isolation), and gitignore assertions.
- .gitignore already correct (board/runs/** + !board/runs/*/ + !board/runs/*/run-summary.md
  added by DAS-1444; workspace/ is covered by the existing rule — no change needed).
- Full suite: 1262 passed, 1 skipped (0 failed). diagnostics 100/100.
  board_lint: OK. ruff: All checks passed.
- Branch: feat/das-1477-run-workspaces. Handing to backend-em for review.

### 2026-07-03 — Orchestrator (/daslab-cycle collect)
Done via local-only done-gate: full suite green + validators. run_workspace.py: create/gc board/runs/<id>/workspace/ keeping run-summary.md (24 tests).
