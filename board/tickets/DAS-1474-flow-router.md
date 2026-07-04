---
id: DAS-1474
title: Flow-router pure-python event-driven trigger router
status: done
assignee: cto
author: ceo
dept: engineering
priority: p1
parent: DAS-1472
goal: organism-ws4-heartbeat
depends_on: [DAS-1473]
zone: flow-router
created: 2026-07-03
updated: 2026-07-03
---

## Description

Build `scripts/flow_router.py` — a PURE-PYTHON (NO LLM) event-driven trigger
router that reads `board/.events.jsonl` and, via a small declarative trigger
table, decides the next operator tempo action: **dispatch next wave**, **run
validators**, or **idle**. This is the "heartbeat" of the ORGANISM WS4 program:
deterministic arrows between autonomous boxes. The router never makes content
decisions and never touches an LLM — it only decides *whether* and *what kind of*
tick should happen next based on the observed event stream.

**Why.** Today wave cadence is operator-driven and implicit. WS4 makes the
tempo explicit, deterministic, and testable so the org can run continuous waves
without a human pressing the button each cycle — while keeping every gate/
interrupt strictly human-owned (fail-safe by construction).

**Embedded context (spec-of-record).** `docs/research/ORGANISM-PROGRAM-PLAN.md`
is the binding spec; this is GATE-3 (P14) work under parent DAS-1472, depends on
DAS-1473, and produces the `flow-router` artifact consumed by DAS-1475.

**Extend-vs-new.** NEW file `scripts/flow_router.py`. Do NOT fork or reimplement
event reading: reuse the existing load-bearing reader `wave_kpi.read_events`
(`scripts/wave_kpi.py`) to parse `board/.events.jsonl`. Per
`docs/adr/0025-events-load-bearing.md`, this operator-tempo reader is
load-bearing but SCOPED — it decides *whether to tick*, it does NOT alter
normal-dispatch decisions. Event emission/shape lives in `scripts/dgox/events.py`;
consume that shape, do not redefine it. Cadence/wave semantics per
`.claude/skills/daslab-cycle/SKILL.md`.

**Triggers (declarative table).** Map each event to a decision:
- `on ticket_created` → consider dispatch of next wave
- `on wave_completed` → run validators / decide next tick
- `on interrupt_answered` → resume (dispatch), never auto-answer
- `on after-N-runs` → periodic validate/idle checkpoint
- `on cron tick` → time-based tick (dispatch / validate / idle)

Decision outputs are exactly: `dispatch` | `validate` | `idle`. Deterministic
arrows (same event stream → same decision), autonomous boxes (each decision
hands off to an already-autonomous executor). Failure-isolated: a malformed
event or reader error degrades to `idle`, never crashes the tempo loop and never
escalates a gate. The router MUST NEVER auto-answer a gate or an interrupt —
those remain human-owned.

**Key files / paths.**
- Build: `scripts/flow_router.py` (+ its tests)
- Reuse: `scripts/wave_kpi.py` (`read_events`)
- Event shape: `scripts/dgox/events.py`
- Event log: `board/.events.jsonl`
- Cadence semantics: `.claude/skills/daslab-cycle/SKILL.md`
- ADR: `docs/adr/0025-events-load-bearing.md`
- Spec: `docs/research/ORGANISM-PROGRAM-PLAN.md`

## Acceptance criteria

- [ ] `scripts/flow_router.py` is pure-python, no LLM call anywhere.
- [ ] Triggers on the 5 event types (`ticket_created`, `wave_completed`,
      `interrupt_answered`, `after-N-runs`, `cron tick`) each map to a
      `dispatch` / `validate` / `idle` decision.
- [ ] Reads events via `wave_kpi.read_events`; does not reimplement event
      parsing or change normal-dispatch decisions (ADR-0025 scope respected).
- [ ] Decisions are deterministic (same event stream → same decision) and
      covered by a test per trigger.
- [ ] Router NEVER auto-answers a gate or an interrupt; failure-isolated
      (malformed event/reader error → `idle`, no crash).
- [ ] Full test suite: 0 failed; diagnostics 100/100.

## Log

### 2026-07-03 — CEO
Created from ORGANISM WS4 HEARTBEAT decomposition (/daslab-plan). Spec-of-record: docs/research/ORGANISM-PROGRAM-PLAN.md.
READ for precision: scripts/wave_kpi.py, scripts/dgox/events.py, .claude/skills/daslab-cycle/SKILL.md, docs/adr/0025-events-load-bearing.md.
GATE-3 (P14). Pure-python (NO LLM) event-driven router over board/.events.jsonl with a declarative trigger table (ticket_created, wave_completed, interrupt_answered, after-N-runs, cron tick) → dispatch / validate / idle. Reads events via wave_kpi.read_events (ADR-0025: load-bearing but scoped — decides WHETHER to tick, not normal-dispatch). Failure-isolated; never auto-answers a gate/interrupt. Tests per trigger. Produces: flow-router (consumed by DAS-1475). Depends on DAS-1473.

### 2026-07-03 — SRE / DevOps Lead
Built `scripts/flow_router.py` (new file) + `tests/test_flow_router.py` (37 tests). Branch `feat/das-1474-flow-router` (local only).

**What it is.** A PURE-PYTHON (no LLM, no network, no clock/timer/thread/loop) decision function. Public API:
- `route(TickContext) -> Decision` — the pure evaluator; `Decision(action, trigger, reason)` where `action ∈ DECISIONS = {dispatch, validate, idle}`.
- `route_from_store(trigger, *, path=None, checkpoint_every=10, pending_work, in_quiet_hours, break_glass_active, per_day_budget_exceeded) -> Decision` — the single place the store is read.
- `read_event_stream(path)` — failure-isolated wrapper over `wave_kpi.read_events` (never re-parses JSONL, never imports `dgox.*`).
- `TickContext` — a frozen dataclass; every fact (trigger, events, safety flags) is an explicit input (determinism, no hidden state).
- CLI `python3 scripts/flow_router.py --trigger <t> [--events P] [--pending-work] [--quiet-hours] [--break-glass] [--budget-exceeded] [--json]` — evaluator/reporter, exit 0, never mutates (like `loop_controller.py`).

**Declarative trigger table (`_HANDLERS`), the 5 triggers → decision:**
- `ticket_created` → dispatch (idle if a wave is in flight, SI-6).
- `wave_completed` → validate (read-only; never gated).
- `interrupt_answered` → dispatch to resume; idle if wave in flight. NEVER auto-answers (SI-7) — it acts only because a human already wrote `resume:`.
- `after_n_runs` → validate on every Nth completed run (run_end count from the stream), else idle.
- `cron_tick` → dispatch if `pending_work`, else validate-if-checkpoint-due, else idle.

**Shadow-rule clean (ADR-0025).** It READS the store (via `wave_kpi.read_events`) only to derive tempo facts — runs-in-flight (SI-6) and completed-run count (after-N-runs) — i.e. WHETHER/what-kind of tick. It writes NO `board/tickets/*.md` routing field and never picks ticket/role/model, so the `test_dgox_phase1_shadow.py` P1 reader-vs-router rule sees "reads but does not route" ⇒ not flagged. Confirmed green.

**SI invariants (ADR-0027).** SI-1 one-shot (no in-process timer/loop; `route()` returns once). SI-3/SI-4/SI-5 dispatch gates (break-glass / quiet-hours / per-day budget) downgrade any tentative dispatch to idle via `_dispatch_blocked`. SI-6 max 1 wave (in-flight → idle). SI-7 the decision alphabet is closed to {dispatch, validate, idle} — structurally no answer/approve action. Failure-isolated: malformed event / unknown trigger / reader error / handler exception → idle, never a crash.

**VERIFY (full, in worktree).** `python3 -m pytest -q` → 1342 passed, 1 skipped (0 failed). `python3 scripts/diagnostics.py` → 100/100. `python3 scripts/board_lint.py` → 0 violations. `python3 scripts/check_loop_mode.py` → exit 0 (loop stays shadow). `ruff check scripts tests` → clean. Committed LOCALLY only (no push).

Handing to CTO for review (my reviewer per ROUTING; GATE-3/P14 work).

### 2026-07-03 — Orchestrator (/daslab-cycle collect)
Done via local-only done-gate: full suite 1342, flow_router.py pure-python (5 triggers, 37 tests), shadow-rule-clean, SI-1..7 honored.
