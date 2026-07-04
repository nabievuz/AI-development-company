---
id: DAS-1478
title: Kill-switch drill and scheduler safety-rail tests
status: done
assignee: cto
author: ceo
dept: engineering
priority: p1
parent: DAS-1472
goal: organism-ws4-heartbeat
depends_on: [DAS-1475]
zone: safety-drill
created: 2026-07-03
updated: 2026-07-03
---

## Description

Add a kill-switch drill plus scheduler safety-rail tests so the ORGANISM WS4
heartbeat can never run away: when break-glass is engaged the scheduler/tick
must halt, the budget and per-day caps must fire, quiet hours must be respected,
and gates/interrupt-cards must never be auto-approved. This is GATE-4 Testing
work for the WS4 heartbeat; it verifies the safety envelope that the loop
controller and flow router operate inside.

**Why:** an autonomous heartbeat is only safe if its stop conditions are proven
by tests, not assumed. We assert the loop stays in its non-live mode and that
every rail is exercised.

**Extend vs new:** EXTEND the existing safety/loop tooling — reuse the current
`break_glass`, `loop_controller`, `check_loop_mode`, `flow_router`, and the
`dgox` event log. Add tests (and a drill entrypoint) rather than new controller
logic. Wire the cheap assertions into CI; keep the expensive end-to-end drill in
a scheduled job.

**Key files/paths (read for precision):**
- `scripts/break_glass.py` — kill-switch engage/disengage.
- `scripts/loop_controller.py` — the tick/loop the drill must halt.
- `scripts/check_loop_mode.py` — must stay exit 0 (never flips to live/auto_apply).
- `scripts/flow_router.py` — reuse for routing/dispatch in tests.
- `scripts/dgox/events.py` — event log scanned for gate/approval violations.
- Reuse `dispatch_emitter` / `flow_router` for the dispatch path.

Spec-of-record: `docs/research/ORGANISM-PROGRAM-PLAN.md`.

## Acceptance criteria

- [x] Break-glass kill-switch drill halts the tick (scheduler/loop stops when break-glass is engaged).
- [x] Budget cap + per-day cap rails are tested and fire.
- [x] Quiet hours are respected (tick suppressed inside quiet window).
- [x] Max-concurrent rail is tested.
- [x] Zero gate/approval violations in the event log (test scans `dgox/events` for auto-approved gates/interrupt-cards → count is 0).
- [x] `check_loop_mode.py` stays exit 0 (loop never flips to live/auto_apply).
- [x] Cheap assertions wired into CI; expensive drill wired into a scheduled drill job.
- [x] Full suite 0 failed, diagnostics 100/100.

## Log

### 2026-07-03 — CEO
Created from ORGANISM WS4 HEARTBEAT decomposition (/daslab-plan). Spec-of-record: docs/research/ORGANISM-PROGRAM-PLAN.md.
READ for precision: scripts/break_glass.py, scripts/loop_controller.py, scripts/check_loop_mode.py, scripts/flow_router.py, scripts/dgox/events.py.
Scope+acceptance (expand; keep frontmatter exact): GATE-4 Testing. Add a kill-switch drill + safety-rail tests: (1) break_glass kill-switch drill — asserting the scheduler/tick halts when break-glass is engaged; (2) budget cap + per-day cap rails fire; (3) quiet hours respected; (4) gates + interrupt-cards are NEVER auto-approved (scan the event log for zero gate/approval violations); (5) check_loop_mode.py stays exit 0 (loop never flips to live/auto_apply). Reuse dispatch_emitter/flow_router. Wire cheap parts into CI, expensive into scheduled drills.
Acceptance: [ ] kill-switch drill halts the tick; [ ] budget/quiet/max-concurrent rails tested; [ ] zero gate/approval violations in the event log (test); [ ] check_loop_mode.py exit 0; [ ] full suite 0 failed, diagnostics 100/100.
Constraints: org-engine, NO project: field.

### 2026-07-03 — QA Lead
GATE-4 Testing built and verified (LOCAL branch feat/das-1478-kill-switch-drill).
Approach: DAS-1475 already shipped `tests/test_scheduler.py` with broad SI-3/4/5/7
tick coverage, so this ticket adds the DEDICATED kill-switch DRILL entrypoint, the
never-auto-approve VIOLATION SCANNER, the missing SI-6 tick-level rail, and the
scheduled drill job — activating the real brakes (no re-implemented controller logic).

Added:
- `scripts/kill_switch_drill.py` — end-to-end drill harness (CLI: `--smoke` / `--iterations N`).
  Six rails, one pass, each against a LIVE (heartbeat_enabled=true) `loop_controller.tick`
  in an isolated temp workspace (never touches board/.events.jsonl, config/loop.yaml, or
  the real config/features.yaml):
    * SI-3 break-glass — engaged override → tick idles; 60-min override AUTO-EXPIRES →
      dispatch resumes (proves the kill-switch is a bounded, not permanent, stop).
    * SI-4 quiet hours — dispatch tick inside the window → idle.
    * SI-5 budget — a seeded opus span (~$5, priced from the real config/budgets.yaml)
      over a $0.01 per-day cap → idle; the per-run cap is asserted present as a hard
      ceiling (per_day >= per_run, tokens+cost > 0).
    * SI-6 max_concurrent_waves — a seeded run_start with no run_end → a new dispatch
      tick idles citing "SI-6" (no stacked/overlapping wave).
    * SI-7 never-auto-approve — `scan_gate_approval_violations()` scans a synthetic
      event log (real routing/run events + a PENDING gate + an UNANSWERED interrupt +
      a genuine human approval) to ZERO violations; a seeded auto-approval
      (approved_by=heartbeat) is DETECTED (positive control — the scanner has teeth);
      the router decision alphabet is the closed {dispatch,validate,idle} set (no
      approve/answer action); and a live tick over the store writes NOTHING (the
      heartbeat structurally cannot sign a gate).
    * SI-2 check_loop_mode.py stays exit 0 (loop.yaml untouched, shadow/auto_apply:false).
- `tests/test_kill_switch_drill.py` — 24 cheap CI assertions (scanner truth table incl.
  pending-gate/human-approval non-violations, closed alphabet, each rail drill, full
  pass, CLI exit codes, and isolation guarantees on board/.events.jsonl + config/loop.yaml).
- `.github/workflows/kill-switch-drill.yml` — scheduled expensive tier (daily 04:37 UTC,
  matrix ubuntu/macos, workflow_dispatch, >=20 passes), mirroring recovery-drill.yml.
- `.github/workflows/ci.yml` — cheap `kill_switch_drill.py --smoke` step wired in next
  to the kill_drill smoke (the 24 pytest assertions also run in the CI Tests step).

VERIFY (all green, local): `python3 -m pytest -q` = 1408 passed, 1 skipped, 0 failed;
`python3 scripts/diagnostics.py` = SCORE 100/100; `python3 scripts/board_lint.py` =
39 tickets, 0 violations; `python3 scripts/check_loop_mode.py` = exit 0;
`ruff check scripts tests` = all checks passed; `py_compile` OK; both workflows parse.
Zero gate/approval-violation proof: `scan_gate_approval_violations(clean_log) == []`
AND the live tick leaves the event store byte-identical (no gate signed).

Committed LOCAL only (no push/PR per dispatch constraint). Routed to CTO for review
(ROUTING: qa-lead → cto). No escalations; no cross-dept impact; no new work discovered.

### 2026-07-03 — Orchestrator (/daslab-cycle collect)
Done. kill_switch_drill.py: 6 SI rails drilled (break-glass auto-expiry, budget caps, quiet hours, max-concurrent, zero gate/approval violations w/ positive control, loop stays shadow) + scheduled workflow (24 CI tests).
