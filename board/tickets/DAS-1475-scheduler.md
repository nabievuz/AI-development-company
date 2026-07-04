---
id: DAS-1475
title: Scheduler with schedule.yaml and loop_controller tick integration
status: done
assignee: sre-lead
author: ceo
dept: engineering
priority: p1
parent: DAS-1472
goal: organism-ws4-heartbeat
depends_on: [DAS-1473, DAS-1474]
zone: scheduler
created: 2026-07-03
updated: 2026-07-03
---

## Description

GATE-3 (P15). Build the organism heartbeat scheduler: a declarative
`board/schedule.yaml` (cron-like entries + after-N-runs triggers) consumed by a
new `scripts/loop_controller.py --tick` path. The `--tick` path consults
`scripts/flow_router.py` and `evaluate_promotion`, and NEVER auto-applies and
NEVER auto-approves — every gate and interrupt-card ALWAYS waits for the Founder.

**Why:** WS4 gives the org a safe, opt-in heartbeat so scheduled ticks can
evaluate promotion/routing without a human kicking each wave, while keeping all
apply/approve decisions human-gated.

**Extend, do not fork:** ADD a `--tick` subpath to the existing
`scripts/loop_controller.py`; reuse `scripts/flow_router.py`,
`scripts/check_loop_mode.py`, `scripts/feature_flags.py`, and
`scripts/break_glass.py`. Do NOT create a parallel controller.

**Hard safety rails (all mandatory):**
- Per-run and per-day budget caps enforced via the cost-ledger.
- Max concurrent waves cap.
- Quiet hours honored.
- `break_glass` kill-switch honored — if tripped, `--tick` is a no-op.
- Never-auto-approve: gates and interrupt-cards ALWAYS wait for the Founder.

Add a heartbeat enable flag to `scripts/feature_flags.py` DEFAULTS, default OFF.
Keep `config/loop.yaml` at `shadow` / `auto_apply: false` so
`scripts/check_loop_mode.py` stays exit 0 — do NOT touch `config/loop.yaml`.
A launchd/cron entry is DOCUMENTED only (not installed).

**Key files/paths:**
- New: `board/schedule.yaml`
- Extend: `scripts/loop_controller.py` (add `--tick`)
- Read/reuse: `scripts/check_loop_mode.py`, `scripts/feature_flags.py`,
  `config/loop.yaml`, `config/features.yaml`, `scripts/flow_router.py`,
  `scripts/break_glass.py`
- Spec-of-record: `docs/research/ORGANISM-PROGRAM-PLAN.md`

**Constraints:** org-engine ticket — NO `project:` field. Tests required.

## Acceptance criteria

- [x] `board/schedule.yaml` + `loop_controller --tick` calling `flow_router` + `evaluate_promotion`
- [x] budget / quiet-hours / break-glass / max-concurrent rails enforced
- [x] heartbeat flag in `feature_flags.py` DEFAULTS (default OFF)
- [x] `check_loop_mode.py` exit 0 (`config/loop.yaml` untouched)
- [x] never auto-applies / never auto-approves (gates + interrupt-cards wait for Founder)
- [x] launchd/cron entry DOCUMENTED (not installed)
- [x] full suite 0 failed, diagnostics 100/100

## Log

### 2026-07-03 — CEO
Created from ORGANISM WS4 HEARTBEAT decomposition (/daslab-plan). Spec-of-record: docs/research/ORGANISM-PROGRAM-PLAN.md.
READ for precision: scripts/loop_controller.py, scripts/check_loop_mode.py, scripts/feature_flags.py, config/loop.yaml, config/features.yaml, scripts/flow_router.py, scripts/break_glass.py.
Scope+acceptance (expand; keep frontmatter exact): GATE-3 (P15). Build the scheduler: board/schedule.yaml (cron-like entries + after-N-runs triggers) consumed by a scripts/loop_controller.py --tick path (ADD a --tick to loop_controller that consults flow_router + evaluate_promotion, NEVER auto-applies). Hard safety rails: per-run + per-day budget caps (cost-ledger), max concurrent waves, quiet hours, break_glass kill-switch honored, never-auto-approve (gates/interrupt-cards ALWAYS wait for the Founder). Add a heartbeat enable flag to scripts/feature_flags.py DEFAULTS (default OFF). Keep config/loop.yaml at shadow/auto_apply:false so check_loop_mode.py stays exit 0 — do NOT touch loop.yaml. A launchd/cron entry is DOCUMENTED (not installed). Tests.
Produces: scheduler (consumed by DAS-1478).

### 2026-07-03 — SRE Engineer
Implemented all acceptance criteria on branch feat/das-1475-scheduler (commit 19457c6):

**Files created:**
- /Users/owner/DasLab/.claude/worktrees/DAS-1475/board/schedule.yaml — declarative trigger table with 5 trigger types (cron_tick, after_n_runs, ticket_created, wave_completed, interrupt_answered), quiet-hours window (22:00–06:00 UTC, SI-4), max_concurrent_waves=1 (SI-6), never_auto_approve=true (SI-7), and documented launchd/cron entry (not installed, SI-1).
- /Users/owner/DasLab/.claude/worktrees/DAS-1475/tests/test_scheduler.py — 42 tests covering all SI-1..SI-7 invariants.

**Files modified:**
- /Users/owner/DasLab/.claude/worktrees/DAS-1475/scripts/loop_controller.py — added --tick path with helper functions: _load_schedule(), _in_quiet_hours() (midnight-wrapping window logic), _per_day_budget_exceeded() (consults cost_ledger, failure-isolated), tick() (pure evaluator — calls flow_router.route_from_store() + evaluate_promotion(), enforces all safety rails), _print_tick(); updated main() with --tick/--trigger/--schedule/--events/--budgets/--pending-work/--json args.
- /Users/owner/DasLab/.claude/worktrees/DAS-1475/scripts/feature_flags.py — added heartbeat_enabled: False to DEFAULTS (ADR-0027 SI-7).
- /Users/owner/DasLab/.claude/worktrees/DAS-1475/config/features.yaml — documented heartbeat_enabled: false.
- /Users/owner/DasLab/.claude/worktrees/DAS-1475/tests/test_feature_flags.py — updated 3 tests for new heartbeat_enabled DEFAULTS key.

**Verification:** pytest 1384 passed, 1 skipped (0 failed). diagnostics.py 100/100. board_lint.py 0 violations. check_loop_mode.py exit 0. ruff clean. config/loop.yaml untouched (mode: shadow, auto_apply: false).

### 2026-07-03 — Orchestrator (/daslab-cycle collect)
Done via local-only done-gate: full suite 1384; --tick + schedule.yaml + SI-1..7 rails; heartbeat_enabled OFF; loop.yaml untouched (check_loop_mode exit 0); 42 tests.
