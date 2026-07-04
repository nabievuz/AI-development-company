---
id: DAS-1473
title: Author ADR-0027 scheduler safety model
status: done
assignee: chairman
author: ceo
dept: engineering
priority: p1
parent: DAS-1472
goal: organism-ws4-heartbeat
zone: docs/adr
created: 2026-07-03
updated: 2026-07-03
---

## Description

**What.** Author `docs/adr/0027-scheduler-safety.md`, the Architecture Decision
Record that pins the safety model for the ORGANISM tempo substrate (WS4
HEARTBEAT). This ADR decides — per the approved §9 default option #3 in the
spec-of-record — that the tempo substrate is a **SHADOW-MODE, operator-invoked
heartbeat**: `scripts/loop_controller.py --tick` driven by an *optional*
launchd/cron entry the Founder chooses to enable. It stays behind
`config/loop.yaml` `mode: shadow` + `auto_apply: false`
(`scripts/check_loop_mode.py` continues to exit 0), and it honors every existing
brake: the `scripts/break_glass.py` kill-switch, quiet hours, per-run/per-day
budget caps (cost-ledger), a max-concurrent-waves cap, and the
never-auto-approve law (gates and interrupt-cards ALWAYS wait for the Founder).
The ADR encodes these as the **binding scheduler invariants**.

**Why.** The heartbeat is the load-bearing autonomy mechanism, so before any
tempo code lands we need a merged, referenceable decision that fixes the safety
envelope. This closes GATE-1 (Planning) for WS4 by making the "NOT a daemon,
shadow-first, human-in-the-loop" stance the architectural contract the
implementation tickets must satisfy.

**Extend vs. new.** NEW ADR file — the highest existing ADR is 0026, so this is
`0027`. It does not modify `loop.yaml`, `check_loop_mode.py`, `break_glass.py`,
or `features.yaml`; it references them as the invariants' enforcement points.
Add the README index row + theme.

**Key files + paths.**
- Write: `docs/adr/0027-scheduler-safety.md` (new) + row in `docs/adr/README.md`.
- Read for precision: `docs/adr/README.md`, `scripts/loop_controller.py`,
  `scripts/check_loop_mode.py`, `config/loop.yaml`, `scripts/break_glass.py`,
  `config/features.yaml`.
- Spec-of-record: `docs/research/ORGANISM-PROGRAM-PLAN.md` (§9 default #3).

Live operation happens ONLY on an explicit Founder flag-flip after a >=3-day
clean shadow window.

## Acceptance criteria

- [x] `docs/adr/0027-scheduler-safety.md` authored (Accepted), with a matching row in
      `docs/adr/README.md` (+ new WS4 theme). (merge pending review — LOCAL-ONLY branch)
- [x] shadow-mode / `auto_apply: false` / never-auto-approve invariants stated
      explicitly (SI-2, SI-7).
- [x] budget caps + quiet hours + break-glass + max-concurrent-waves encoded as
      binding scheduler invariants (SI-5, SI-4, SI-3, SI-6).
- [x] "NOT a daemon" honored (operator-invoked `--tick`, optional launchd/cron,
      live only on explicit Founder flag-flip after a >=3-day clean shadow window) (SI-1, SI-7).
- [x] diagnostics 100/100.

## Log

### 2026-07-03 — CTO
Authored `docs/adr/0027-scheduler-safety.md` (GATE-1 Planning artifact, Accepted). Decided per §9 default #3: the ORGANISM tempo substrate (WS4 HEARTBEAT) is a SHADOW-MODE, operator-invoked heartbeat (`loop_controller.py --tick` via an OPTIONAL, Founder-enabled launchd/cron entry) — NOT a daemon. Encoded seven binding scheduler invariants:
- SI-1 one-shot `--tick`, at most one wave, no in-process/wall-clock timer (cadence lives only in the external Founder-owned OS entry).
- SI-2 `loop.yaml` stays `shadow` + `auto_apply:false` → `check_loop_mode.py` stays exit 0; heartbeat CALLS `loop_controller.evaluate_promotion` (never reimplements the ≥7-clean-day/GATE-6 rule); heartbeat never flips `loop.yaml`.
- SI-3 break-glass kill-switch (`break_glass.is_active`) honored — a live override halts all autonomous dispatch.
- SI-4 quiet hours (mechanism in the future `board/schedule.yaml`; tick inside window → idle).
- SI-5 per-run/per-day budget caps (`budgets.yaml` caps + `scripts/cost/cost_ledger.py`/`check_cost.py`) as a hard dispatch ceiling.
- SI-6 `max_concurrent_waves = 1` — no overlapping heartbeat waves.
- SI-7 never-auto-approve: gates + interrupt-cards ALWAYS wait for the Founder; ships behind a `features.yaml` flag (default OFF, ADR-0019); live ONLY on an explicit Founder flag-flip after a ≥3-day clean shadow window — kept explicitly DISTINCT from `loop_controller`'s ≥7-day loop-promotion clock.
Constrains — never edits — `loop.yaml`/`check_loop_mode.py`/`break_glass.py`/`features.yaml`/`budgets.yaml`. Added the README index row + a new "Autonomous tempo — ORGANISM WS4 HEARTBEAT" theme.
Numbering: plan text calls this "ADR-0026" but 0026 is already communication-flows (Accepted) → this is 0027 (cockpit becomes 0028); recorded the reassignment in the ADR.
VERIFY (full suite, all green): pytest 1238 passed / 1 skipped; diagnostics 100/100; board_lint 0 (39 tickets); ruff scripts+tests clean; `check_loop_mode.py` exit 0 (mode 'shadow', auto_apply false). All five acceptance criteria met.
Committed LOCAL-ONLY on branch `feat/das-1473-adr-0027-scheduler-safety` (strict local-only — no push/PR per dispatch directive). Status → in_review, assignee → ceo (reviewer per ROUTING.md; CTO's manager). Note for orchestrator: this GATE-1 Planning ADR closes the WS4 safety envelope; downstream WS4 tickets (O4-T02 flow-router → sre-lead, O4-T03 scheduler → sre-eng, O4-T06 safety-rail drills → qa-lead) build against SI-1…SI-7. §9 Q3 COO consult recorded in-ADR (GATE-6 Maintenance Accountable).

### 2026-07-03 — CEO
Created from ORGANISM WS4 HEARTBEAT decomposition (/daslab-plan). Spec-of-record: docs/research/ORGANISM-PROGRAM-PLAN.md.
READ for precision: docs/adr/README.md, scripts/loop_controller.py, scripts/check_loop_mode.py, config/loop.yaml, scripts/break_glass.py, config/features.yaml.
Scope+acceptance (expand; keep frontmatter exact): GATE-1 Planning. Author docs/adr/0027-scheduler-safety.md deciding (per approved §9 default #3): the tempo substrate = a SHADOW-MODE operator-invoked heartbeat (loop_controller.py --tick via an optional launchd/cron entry the Founder enables), staying config/loop.yaml mode:shadow + auto_apply:false (check_loop_mode.py stays exit 0), honoring break_glass kill-switch + quiet hours + per-run/per-day budget caps (cost-ledger) + max concurrent waves + the never-auto-approve law (gates/interrupt-cards ALWAYS wait for Founder). Live only on an explicit Founder flag-flip after a >=3-day clean shadow window. Encode these as the binding scheduler invariants. README index row + theme (highest ADR is 0026; you author 0027).
Acceptance: [ ] ADR-0027 merged + README row; [ ] shadow-mode/auto_apply:false/never-auto-approve invariants explicit; [ ] budget caps + quiet hours + break-glass + max-concurrent encoded; [ ] "NOT a daemon" honored; [ ] diagnostics 100/100.

### 2026-07-03 — Orchestrator (triage)
Reassigned reviewer ceo->chairman (ceo is the author; escalate one level per ROUTING, consistent with ADR-0023/0024/0026 GATE-1 reviews).

### 2026-07-03 — Chairman of the Board
GATE-1 (Planning) sign-off — VERDICT: PASS. Reviewed `docs/adr/0027-scheduler-safety.md` + `docs/adr/README.md` against ticket acceptance and the GATE-1 checklist.

Seven scheduler invariants verified as stated and correctly framed:
- SI-1 operator-invoked one-shot `--tick`, at most one wave, no long-lived process / in-process wall-clock loop / self-rescheduling timer; cadence lives ONLY in an optional, Founder-owned OS (launchd/cron) entry, off by default — the "NOT a daemon" law is honored.
- SI-2 heartbeat never edits `loop.yaml`; loop stays `mode: shadow` + `auto_apply: false` → `check_loop_mode.py` stays exit 0; heartbeat CALLS `loop_controller.evaluate_promotion` (never reimplements the ≥7-clean-day/GATE-6 rule) and never flips `loop.yaml`; loop-mode promotion kept explicitly orthogonal to heartbeat go-live.
- SI-3 break-glass `is_active(now)` consulted (read-only) before dispatch — a live override halts all autonomous dispatch.
- SI-4 quiet-hours window → tick inside window evaluates to idle (mechanism in the future `board/schedule.yaml`).
- SI-5 per-run + per-day budget caps (`budgets.yaml` caps + `cost_ledger.py`/`check_cost.py`) as a hard, self-imposed dispatch ceiling.
- SI-6 `max_concurrent_waves = 1` — a tick fired while a prior heartbeat wave is in flight is idle; zone-collision rule still holds within the single wave.
- SI-7 never-auto-approve absolute: gates + interrupt-cards ALWAYS wait for the Founder; ships behind a `features.yaml` flag (default OFF, ADR-0019); live ONLY on an explicit Founder flag-flip after a ≥3-day clean shadow window, kept distinct from `loop_controller`'s ≥7-day loop-promotion clock.

Constrains-not-edits confirmed at the diff level: merge commit 7bd1c75 touches ONLY the ADR, README index, and this ticket — `loop.yaml` / `check_loop_mode.py` / `break_glass.py` / `features.yaml` / `budgets.yaml` untouched. README index row (0027) + new "Autonomous tempo — ORGANISM WS4 HEARTBEAT" theme present and links resolve. Numbering correct: 0026 is communication-flows (Accepted), so scheduler-safety is 0027; reassignment recorded in the ADR's numbering note.

VERIFY (all green): diagnostics.py 100/100; board_lint 0 violations (39 tickets); check_loop_mode.py exit 0 (mode 'shadow', auto_apply false); pytest 1305 passed / 1 skipped / 0 failed. All five acceptance criteria met.

GATE-1 Planning for WS4 HEARTBEAT is CLOSED. Status → done. Downstream WS4 implementation tickets (O4-T02 flow-router, O4-T03 scheduler, O4-T06 safety-rail drills) build against SI-1…SI-7. Strict local-only: ticket edit + local commit; no push/PR.
