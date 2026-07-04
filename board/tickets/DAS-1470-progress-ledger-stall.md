---
id: DAS-1470
title: Progress-ledger and stall-to-replan rule with check_ledger validator
status: done
assignee: cpo
author: ceo
dept: engineering
priority: p1
parent: DAS-1463
goal: organism-ws2-loom
depends_on: [DAS-1469]
zone: ledger-progress
created: 2026-07-03
updated: 2026-07-03
---

## Description

**What & why.** ORGANISM WS2 "LOOM" gives `/daslab-cycle` an *inner loop* that can
tell whether the org is actually making progress or spinning in place, and can
self-correct by regenerating its plan — or, when regeneration is exhausted, hand
control back to the Founder rather than burn the run. This ticket is **GATE-3
(P7 inner loop)**: after every wave an **opus** planner emits a
`progress-ledger.json` describing the loop state, a **new** validator
(`scripts/check_ledger.py`) validates it against a fixed schema, and a **stall
rule** decides whether to keep going, replan, or pause-on-stall.

**Embedded context (the mechanism).**
- After each wave the (opus) planner writes `progress-ledger.json` with the
  schema `{request_satisfied, in_loop, progress_being_made, next_tickets[],
  instruction}`.
  - `request_satisfied` (bool) — the original request is fully served; the loop
    may terminate cleanly.
  - `in_loop` (bool) — the org is repeating itself / cycling without new ground.
  - `progress_being_made` (bool) — measurable forward motion this wave.
  - `next_tickets` (array<string>) — the ticket ids the next wave should run
    (may be empty when `request_satisfied`).
  - `instruction` (string) — the natural-language steer handed to the next wave.
- **STALL RULE (counter update):**
  `in_loop || !progress_being_made  →  stall = stall + 1`,
  else `stall = max(0, stall - 1)`.
- **REPLAN trigger:** when `stall > 3`, regenerate the **task-ledger**
  (facts-update + plan-update — the same two-section regeneration the ledger
  supports), append a `REPLANNED` event, and **decrement** a bounded
  `max_replans` budget.
- **PAUSE-ON-STALL:** when `max_replans` is exhausted (reaches 0), raise an
  **interrupt-card** to the Founder (`board/interrupts/<id>.json`, per the
  WS1 card schema) instead of replanning again — the run halts awaiting a
  human `resume:<value>` rather than looping forever.

**Extend-vs-new.**
- **NEW:** `scripts/check_ledger.py` — the `progress-ledger.json` schema
  validator (no existing validator covers this shape).
- **EXTEND (do not fork):**
  - `scripts/task_ledger.py` — reuse its facts-update / plan-update
    regeneration entry points for the REPLAN step; do not build a parallel
    ledger writer. (**Note:** `scripts/task_ledger.py` does not yet exist in the
    tree — it is produced by the upstream `depends_on` ticket **DAS-1469**;
    build against the module it lands, extending rather than re-implementing.)
  - `scripts/pulse_checkpoint.py` — the wave-boundary hook. The stall counter,
    `progress-ledger.json` emission, and `pending_interrupts` surfacing align
    with the existing wave-checkpoint discipline (`write_wave_checkpoint`,
    `pending_interrupts`). Emit ledger/REPLAN events through the same typed
    builders in `scripts/dgox/events.py` — no raw event dicts.
  - `board/interrupts/` — reuse the existing interrupt-card schema
    (`board/interrupts/schema.json`) and the `interrupted` status transitions
    for pause-on-stall; do not invent a second halt mechanism.
- **UNCHANGED, but respect:** `scripts/board_lint.py` — org-engine ticket, so
  **no `project:` field** (board_lint R9 forbids it on `board/tickets/`).

**Key files (paths).**
- `scripts/check_ledger.py` — NEW validator (this ticket).
- `scripts/task_ledger.py` — task-ledger regeneration (facts/plan update); from DAS-1469.
- `scripts/pulse_checkpoint.py` — wave-boundary checkpoint writer to extend.
- `scripts/dgox/events.py` — typed event builders (add/reuse for `REPLANNED`).
- `board/interrupts/README.md`, `board/interrupts/schema.json` — interrupt-card contract.
- `scripts/board_lint.py` — R9 (no `project:` on platform tickets).
- `docs/research/ORGANISM-PROGRAM-PLAN.md` — spec-of-record (WS2 LOOM).

## Acceptance criteria

- [ ] `progress-ledger.json` schema `{request_satisfied, in_loop, progress_being_made, next_tickets[], instruction}` defined, and `scripts/check_ledger.py` validates a ledger against it (rejects missing/wrong-typed fields, accepts a well-formed ledger).
- [ ] Stall counter implemented: `in_loop || !progress_being_made → stall+1`, else `stall = max(0, stall-1)`; when `stall > 3`, the task-ledger is regenerated (facts-update + plan-update) and a `REPLANNED` event is appended.
- [ ] `max_replans` is a bounded budget decremented on each replan; on exhaustion an interrupt-card is raised to the Founder (pause-on-stall) instead of replanning again.
- [ ] Test: a synthetic stalled run triggers `REPLANNED` within `<= 2` waves, and triggers pause-on-stall (interrupt-card) once the `max_replans` budget is exhausted.
- [ ] Full suite `0 failed`; diagnostics `100/100`.
- [ ] Org-engine ticket: no `project:` field (board_lint R9 clean); all emitted events go through `scripts/dgox/events.py` typed builders (no raw event dicts).

## Log

### 2026-07-03 — CEO
Created from ORGANISM WS2 LOOM decomposition (/daslab-plan). Spec-of-record: docs/research/ORGANISM-PROGRAM-PLAN.md.
To write precise criteria + paths, READ: scripts/task_ledger.py, scripts/pulse_checkpoint.py, scripts/board_lint.py, board/interrupts/README.md.

### 2026-07-03 — Senior Product Manager
Shipped the P7 inner loop as a LIBRARY + validator. Work (LOCAL-only branch
`feat/das-1470-progress-ledger`, committed, NOT pushed — strict local-only):

- **NEW `scripts/check_ledger.py`** — progress-ledger validator + inner-loop
  engine.
  - `validate_ledger()` enforces the fixed schema
    `{request_satisfied, in_loop, progress_being_made, next_tickets[], instruction}`
    (rejects missing/wrong-typed fields; booleans must be genuine bools, not
    truthy ints; `next_tickets` a list of non-empty strings). CLI exits 0/1/2.
  - `update_stall()` = the stall rule: `in_loop || !progress → stall+1`, else
    `max(0, stall-1)`.
  - `step_inner_loop()` / `run_inner_loop()` — per-wave decision: `satisfied`
    terminates; `stall > 3` with budget → REPLAN; budget exhausted → pause.
  - REPLAN **reuses `scripts/task_ledger.py`** (`update_task_ledger`,
    facts-update + plan-update — no parallel writer): new plan = ledger
    `next_tickets`, a `known` fact records the stall replan, `revision` bumps.
    `max_replans` (bounded, default 2) decrements; stall resets to 0.
  - PAUSE-ON-STALL raises a **DAS-1446 interrupt-card** (`board/interrupts/<id>.json`,
    schema-conforming; unique `<anchor>-stall-<n>` ids) — reuses the existing
    halt mechanism, no second one invented.
- **EXTEND `scripts/dgox/events.py`** — new typed `replanned` event
  (`build_replanned` / `validate_replanned`, added to `_VALID_EVENT_TYPES`). All
  emitted events go through the typed builder — no raw event dicts.
- **NEW `tests/test_check_ledger.py`** (27 tests): schema accept/reject, stall
  rule, write/read round-trip, and the acceptance run — a synthetic stalled run
  triggers `REPLANNED` within ≤2 waves and pause-on-stall (interrupt-card) once
  `max_replans` is exhausted.

VERIFY (full suite): `pytest` 1132 passed / 1 skipped; `diagnostics.py` 100/100;
`board_lint.py` 0 violations (32 tickets); `ruff check scripts tests` clean.

FOLLOW-UP (not done here, by directive): the `/daslab-cycle` wiring point —
after each wave, have the (opus) planner emit `progress-ledger.json`, run
`check_ledger`, and call `step_inner_loop` at the wave boundary (alongside
`write_wave_checkpoint`) — belongs in `.claude/skills/daslab-cycle/SKILL.md`,
which **DAS-1471 owns this wave**. Left untouched to avoid a same-wave conflict;
route the SKILL wiring to DAS-1471 / a subsequent ticket.

Status → in_review; assignee → cpo (reviewer per ROUTING; never self-review).

### 2026-07-03 — Orchestrator (/daslab-cycle collect)
Done via local-only done-gate: full suite 1201 pass + validators green + merge verification. progress-ledger + check_ledger.py + stall rule (stall>3->replan, bounded max_replans->interrupt-card) + `replanned` event; library+validator, cycle-wiring documented as follow-up.
