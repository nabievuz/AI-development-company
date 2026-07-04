---
id: DAS-1472
title: ORGANISM WS4 — HEARTBEAT (autonomous tempo)
status: done
assignee: cto
author: ceo
dept: engineering
priority: p1
parent: 
goal: organism-ws4-heartbeat
created: 2026-07-03
updated: 2026-07-03
---

## Description

**EPIC.** WS4 — HEARTBEAT gives DasLab an *autonomous tempo* and kills gap **G2**
(no self-pacing: today the org only moves when an operator manually invokes a wave).
It is one AADL-stage-gated epic in Program ORGANISM (v1.0.0 → v2.0.0), decomposed per
the spec-of-record `docs/research/ORGANISM-PROGRAM-PLAN.md` §4 WS4.

**What it delivers (patterns P14–P16):**
- **P14 flow-router** — a *pure-Python, no-LLM* router over `board/.events.jsonl` that
  triggers on `ticket_created` / `wave_completed` / `interrupt_answered` / `after-N-runs`
  / cron and decides: dispatch / validate / idle. Deterministic, testable.
- **P15 scheduler** — `board/schedule.yaml` (cron + after-N-runs) that drives
  `loop_controller.py --tick`. It **must call `loop_controller.evaluate_promotion` as the
  governance gate** and stay under `check_loop_mode.py`.
- **P16 run-workspaces** — `board/runs/<id>/workspace/` scratch space, GC'd on run close,
  final summary retained.

**EXTEND, DO NOT DUPLICATE — activate the existing loop machinery.** The promotion
evaluator (`scripts/loop_controller.py`), the OFF-tripwire (`scripts/check_loop_mode.py`),
and the SSOT (`config/loop.yaml`) already exist and are load-bearing. WS4 *activates* them:
- `loop_controller.py` is an **evaluator/reporter that never mutates** (always exit 0). The
  7-clean-day + human-approved GATE-6 promotion rule (`evaluate_promotion`,
  `clean_live_days`, `has_approved_promotion_record`) is NOT to be reimplemented — the
  heartbeat *calls* it as the gate.
- `check_loop_mode.py` forbids `mode ∈ {limited_live, full}` and requires
  `auto_apply == false`. It MUST stay **exit 0** through every WS4 change.
- `config/loop.yaml` stays `mode: shadow`, `auto_apply: false`. Editing it is a
  governance change — human-only (QONUN-5).
- New heartbeat feature flag goes into `scripts/feature_flags.py` `DEFAULTS`, default **OFF**.

**HARD SAFETY (approved §9 default #3 + QONUN-5).** The heartbeat may **READ** metrics and
**dispatch** waves, but flipping `loop.yaml` to a live mode or setting `auto_apply: true` is
**human-only and FORBIDDEN to automate**. Gates and interrupt-cards **always** wait for the
Founder — the heartbeat never auto-approves a gate. The **"NOT a daemon" law is honored**:
the tempo substrate is a **shadow-mode, operator-invoked `--tick`** (an optional
launchd/cron entry the Founder enables), not a background timer that acts on its own. Live
promotion (shadow → live) happens only on the Founder's explicit flag flip after a ≥3-day
clean shadow window (T1 ≥ 0.60 ∧ T2 ≤ 0.15 ∧ T7 hold on the rolling window).

**Children (materialized by /daslab-plan): DAS-1473 … DAS-1478**, mapping the WS4
decomposition O4-T01 … O4-T07:
- DAS-1473 — **P** ADR-0026 scheduler-safety model (budget caps, quiet hours, break-glass,
  never-auto-approve, `auto_apply:false` invariants; `check_loop_mode` stays green).
- DAS-1474 — **Dev** P14 flow-router (pure-Python, deterministic routing over events).
- DAS-1475 — **Dev** P15 scheduler (`board/schedule.yaml` → `loop_controller.py --tick`;
  calls `evaluate_promotion`; heartbeat flag in `feature_flags DEFAULTS` OFF; loop.yaml stays
  shadow / `auto_apply:false`).
- DAS-1476 — **Dev** `board/.metrics-history.jsonl` feeder (oldest→newest, exact
  `YYYY-MM-DDTHH:MM:SSZ`) so the clean-day streak computes correctly.
- DAS-1477 — **Dev** P16 run-workspaces (`board/runs/<id>/workspace/` scratch, GC on close,
  summary retained).
- DAS-1478 — **T** kill-switch drill + safety-rail tests (budget/day caps, quiet hours,
  gates never auto-approved) → zero gate/approval violations in the event log.
- (The **Dep** shadow-run ≥3 days → Founder flag flip is a Founder gate, O4-T07, not an
  agent-executable child.)

**Key files + paths:**
- Spec-of-record: `docs/research/ORGANISM-PROGRAM-PLAN.md` (§4 WS4, §9 Q3).
- Extend/activate: `scripts/loop_controller.py`, `scripts/check_loop_mode.py`,
  `config/loop.yaml`, `scripts/feature_flags.py`.
- New: `board/schedule.yaml`, `board/runs/<id>/workspace/`,
  `board/.metrics-history.jsonl` feeder, the flow-router script.
- Consumes event data from WS1/WS3 (`board/.events.jsonl`, `scripts/wave_kpi.py`).
- ADR: 0026 (scheduler safety) → row in `docs/adr/README.md`.

**Extend-vs-new verdict:** EXTEND for the loop trio + feature_flags; NEW only for
flow-router, scheduler config, metrics-history feeder, and run-workspaces.

**Constraints:** org-engine work → `board/tickets/` only, **NO `project:` field** (board_lint
R9). Depends on WS1 (durable runs) + WS3 (live event emitter) landing first per the strict
build order WS1 → WS3 → WS2 → **WS4**.

## Acceptance criteria

- [ ] AADL 6-gate closure logged for the WS4 epic (Planning → Design → Development → Testing
      → Deployment → Maintenance), each gate checklist recorded in the epic note.
- [ ] Children DAS-1473 … DAS-1478 planned, each stage-tagged with owner-hints per the §4
      WS4 table; models passed explicitly on dispatch.
- [ ] ADR-0026 (scheduler safety) merged with a row in `docs/adr/README.md`.
- [ ] P14 flow-router is pure-Python (no LLM) and passes a deterministic routing test over
      synthetic `board/.events.jsonl` inputs.
- [ ] P15 scheduler drives `loop_controller.py --tick` and calls
      `loop_controller.evaluate_promotion` as the promotion gate — the 7-clean-day / GATE-6
      rule is reused, never reimplemented.
- [ ] A heartbeat feature flag is added to `scripts/feature_flags.py` `DEFAULTS`, default OFF.
- [ ] `board/.metrics-history.jsonl` feeder writes oldest→newest with exact
      `YYYY-MM-DDTHH:MM:SSZ` timestamps; the clean-day streak computes correctly.
- [ ] P16 run-workspaces scratch dir is created per run and GC'd on close; final summary
      retained (GC test passes).
- [ ] **`config/loop.yaml` stays `mode: shadow`, `auto_apply: false`; no automated path can
      flip it to live or `auto_apply: true`.**
- [ ] **`python3 scripts/check_loop_mode.py` stays exit 0** across every WS4 change.
- [ ] Kill-switch drill passes; safety-rail tests (budget/day caps, quiet hours, gates
      never auto-approved) all green.
- [ ] **Zero gate/approval violations in the event log** — the heartbeat never auto-approves
      a gate or interrupt-card; the Founder always decides.
- [ ] "NOT a daemon" law honored: tempo is operator-invoked shadow-mode `--tick`, not a
      self-acting background timer.
- [ ] `diagnostics.py` remains 100/100; `board_lint` passes (no `project:` field; org-engine
      placement).

## Log

### 2026-07-03 — CEO

Created from ORGANISM WS4 HEARTBEAT decomposition (/daslab-plan). Spec-of-record: docs/research/ORGANISM-PROGRAM-PLAN.md.
READ for precision: docs/research/ORGANISM-PROGRAM-PLAN.md, scripts/loop_controller.py, scripts/check_loop_mode.py, config/loop.yaml.

EPIC. Autonomous tempo — kills gap G2. Patterns P14 (flow-router), P15 (scheduler), P16
(run-workspaces). ACTIVATE the existing loop machinery (loop_controller.py +
check_loop_mode.py + config/loop.yaml), do NOT duplicate. Spec-of-record:
ORGANISM-PROGRAM-PLAN.md §4 WS4. Children DAS-1473..1478. HARD SAFETY (approved §9 default #3
+ QONUN-5): the heartbeat may READ metrics + dispatch waves but flipping loop.yaml to live or
auto_apply:true is human-only and FORBIDDEN to automate; check_loop_mode.py must stay exit 0;
gates + interrupt-cards ALWAYS wait for the Founder; "NOT a daemon" law honored (shadow-mode
operator-invoked --tick). Acceptance = AADL 6-gate closure + kill-switch drill passes + zero
gate/approval violations in the event log.

### 2026-07-03 — Orchestrator (/daslab-run)
Done. EPIC CLOSED — WS4 HEARTBEAT complete. ADR-0027 (SI-1..7 scheduler safety); flow_router.py (5 triggers, pure-python); scheduler --tick + schedule.yaml + safety rails; metrics-history feeder; run-workspaces; kill-switch drill. heartbeat_enabled OFF (Founder flag-flip after >=3-day clean window); loop stays shadow/auto_apply:false (QONUN-5 + NOT-a-daemon honored). Children DAS-1473..1478 done.
