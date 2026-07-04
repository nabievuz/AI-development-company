---
id: DAS-1451
title: Kill-drill in check_recovery + fork-drill (T5 gate)
status: done
assignee: cto
author: ceo
dept: engineering
priority: p1
parent: DAS-1440
goal: organism-ws1-pulse
depends_on: [DAS-1444, DAS-1445]
zone: scripts/recovery
created: 2026-07-03
updated: 2026-07-03
---

## Description

**AADL stage: GATE-4 Testing.**

The ORGANISM program needs the T5 recovery-reliability gate to be scored by a
**real** kill/resume drill, not just by passively replaying whatever routing
transitions already happen to be in the event store. Today `scripts/check_recovery.py`
computes T5 = `successful_replays / recovery_drills` (target ≥ 0.99, guardrail:
zero corrupted resumes) and is **inert** (exit 0) until `recovery_drill` events
exist. `scripts/replay_qa.py` can emit those events, but only from pre-existing
`routing_decision` chains — nothing exercises a genuine mid-wave crash and
`--resume`. This ticket makes the gate meaningful by driving actual kill and
fork drills that produce the `recovery_drill` events the existing gate scores.

**What & why.** Add a real drill harness that (a) starts a synthetic 3-wave run,
(b) `kill -9`s it mid-wave-2, (c) resumes via `--resume`, and (d) asserts the
resumed run lost **zero** tickets and duplicated **zero** tickets. Then add a
**fork-drill**: fork from a wave-1 checkpoint, run it forward to a divergent
outcome, and confirm the original run is left intact. Both drills emit
`recovery_drill` events so the existing T5 computation in
`metrics_lib.recovery_reliability()` (and thus `check_recovery.py`) scores them.
This turns T5 from a shipped-but-inert lever into a gate backed by live evidence,
per the ORGANISM WS1 pulse plan.

**Extend-vs-new posture: EXTEND, do not replace.**
- Keep `metrics_lib.recovery_reliability()` and `check_recovery.py`'s scoring/exit
  contract exactly as-is — they already read `recovery_drill` events, honor the
  zero-corrupted guardrail, and stay inert when unmeasured. Do not fork the T5
  math.
- Reuse the `recovery_drill` event shape emitted by `replay_qa.py`
  (`event_type: "recovery_drill"`, `outcome: "success"|"fail"`, `corrupted: bool`,
  plus `run_id`, `ticket_id`, `created_at`). New drills MUST emit this same shape
  (via `replay_qa --emit` or an equivalent writer) so no gate change is needed to
  score them.
- Add the drill driver as a new, self-contained module/entrypoint under the
  `scripts/recovery` zone. Wiring it *through* `check_recovery.py` (e.g. a
  `--drill`/`--run-drills` flag that generates events then scores) is acceptable
  as long as the default no-arg behavior of `check_recovery.py` is unchanged.

**Key existing files this touches (paths):**
- `scripts/check_recovery.py` — the T5 gate CLI. Currently: reads
  `board/.events.jsonl`, calls `metrics_lib.recovery_reliability(...)`, prints
  inert message + exit 0 when `None`, else OK/FAIL on `ratio >= target and
  corrupted == 0`. Extend to drive/consume the new drills without breaking the
  existing default path.
- `scripts/replay_qa.py` — recovery-drill harness. `drill()` groups
  `routing_decision` events by `run_id`/`ticket_id`, `replay_run()` detects a
  broken transition chain (corrupted resume), and `--emit` appends
  `recovery_drill` events. `VALID_STATUSES = {backlog, todo, in_progress,
  blocked, in_review, done}`. Reuse `--emit` as the event writer.
- `scripts/metrics_lib.py` — `recovery_reliability(events)` (lines ~181-192):
  filters `event_type == "recovery_drill"`, counts `corrupted`, counts `ok`
  (`outcome == "success"` AND not `corrupted`), returns
  `{ratio, successful, drills, corrupted}` or `None`. Do NOT change this shape.
- Event store: `board/.events.jsonl` (default `--events`); drill events should be
  emittable into a throwaway store for CI and/or the live store for scheduled runs.
- CI/drills wiring: add the cheap drill to the existing CI workflow and the
  expensive (≥20-iteration) drill to a scheduled workflow under `.github/`.

**Cost tiering.** The kill/resume drill and the ≥20-iteration T5 accumulation are
expensive; the fast smoke variant is cheap. Put the **cheap** smoke drill into CI
(runs on every PR) and the **expensive** ≥20-iteration + fork drill into a
**scheduled** workflow, so PR latency stays low while T5 still accrues real data.

## Acceptance criteria

- [ ] **Kill-mid-wave-2 drill exists and passes:** a new drill starts a synthetic
      3-wave run, `kill -9`s it during wave 2, `--resume`s it, and asserts **zero
      lost tickets** and **zero duplicated tickets** across the resume boundary.
- [ ] **T5 ≥ 0.99 over ≥ 20 iterations:** running the drill ≥ 20 times emits ≥ 20
      `recovery_drill` events such that `check_recovery.py` reports T5 `ratio ≥
      0.99` with `corrupted == 0` (gate exit 0).
- [ ] **Fork-drill:** forking from a wave-1 checkpoint produces a divergent run
      whose outcome differs from the original, while the original run remains
      intact (unmodified checkpoint/state, still independently replayable).
- [ ] **Events emitted + scored:** both drills emit `recovery_drill` events in the
      shape consumed by `metrics_lib.recovery_reliability()` (via `replay_qa
      --emit` or equivalent), and `check_recovery.py` scores them (a corrupted
      resume yields `corrupted > 0` → FAIL exit 1, honoring the guardrail).
- [ ] **CI/scheduled wiring:** the cheap smoke drill runs in CI on every PR; the
      expensive ≥20-iteration + fork drill runs on a scheduled workflow. Both are
      green.
- [ ] `check_recovery.py`'s existing default (no-arg) behavior and its scoring/exit
      contract are unchanged; `metrics_lib.recovery_reliability()` return shape is
      unchanged.
- [ ] Consumes the outputs of DAS-1444 (wave-checkpoints) and DAS-1445
      (resume-fork); no re-implementation of checkpointing or fork mechanics here.

## Log

### 2026-07-03 — CEO
Created from ORGANISM program-plan decomposition (/daslab-plan). Spec-of-record: docs/research/ORGANISM-PROGRAM-PLAN.md.

### 2026-07-03 — QA Lead
Built a REAL kill/resume + fork drill and wired it into the existing T5 gate. All
acceptance criteria met; full suite green. Set `status: in_review`, `assignee: cto`
(ROUTING — my manager; never review my own work). Local-only, no push/PR.

**New:** `scripts/kill_drill.py` (drill driver), `tests/test_kill_drill.py` (13
tests), `.github/workflows/recovery-drill.yml` (scheduled expensive tier). Edited
`.github/workflows/ci.yml` (cheap smoke step) and `tests/test_dgox_phase1_shadow.py`
(`_EVENT_PRODUCERS += kill_drill.py`). No change to `check_recovery.py`,
`metrics_lib.recovery_reliability()`, `replay_qa.py`, `pulse_checkpoint.py`, or
`resume_fork.py` — EXTEND, not replace.

**Drill design (kill-mid-wave-2).** `run_kill_drill` writes a synthetic-run spec
and spawns a REAL child (`--worker`) that drives a 3-wave run, durably
(O_APPEND+fsync) emitting `routing_decision` events (via the dgox typed builder) +
per-ticket `ticket_completion` records (via `pulse_checkpoint`, DAS-1444), with a
wave-boundary checkpoint each wave. Mid-wave-2 the child issues a genuine
`os.kill(getpid, SIGKILL)` — no cleanup/atexit/flush; the parent confirms death by
`returncode == -9`. The parent then resumes via `resume_fork.resume_run` (DAS-1445),
which replays the durable log + completion records and returns only the tickets
still needing work; it re-dispatches exactly those (resuming started-but-unfinished
tickets from their last recorded status, cold-starting never-started ones), skipping
anything durably terminal in the log or already recorded complete (idempotent — the
DAS-1447 guard-before-act window is covered by the `after_done` idempotency test).

**Zero lost / zero duplicated.** Verified per-ticket via `replay_qa.replay_run`
(reused, not re-implemented): every planned ticket reaches a terminal state (zero
lost), no ticket's transition chain is corrupted, and every ticket has exactly one
completion record (zero duplicated). A double-dispatch would surface as a
`done -> todo` broken chain → corrupted → gate FAIL, so the guardrail is live.

**T5 result.** `--iterations 20` → 20 kill drills + 1 fork drill = 21
`recovery_drill` events; `check_recovery.py` reports **ratio 1.000 ≥ 0.99, corrupted
0 over 21 drills, exit 0**. Every iteration: `killed=True, zero_lost=True,
zero_dup=True, chain_clean=True`. (~2s for 20 iters.)

**Fork-drill divergence proof.** Base run takes DAS-8501 `in_progress`(wave-1) →
`done`(wave-2). `resume_fork.fork_run` at wave-1 mints a new run_id inheriting
`{DAS-8501: in_progress}`; the fork is driven to `blocked` in its OWN event store +
checkpoint tree. Divergence: fork final `{DAS-8501: blocked}` ≠ original
`{DAS-8501: done}`. Original intact: base event store + both checkpoints
byte-identical before/after, still replays clean to `done`, fresh run_id ≠ base.

**Event emission.** `emit_recovery_drill` writes the EXACT `replay_qa --emit` shape;
the outcome/corrupted verdict is derived from `replay_qa.replay_run` PER TICKET
(replay_qa's top-level `drill()` groups a whole run as one chain — correct for its
single-ticket runs, wrong for a multi-ticket drill run, so the ticket's sanctioned
"equivalent writer" path is used). Interop with the shipped `replay_qa --emit` is
proven on the single-ticket fork store (test). Corrupted-resume → gate exit 1 is
tested. `check_recovery.py` default no-arg path stays inert (exit 0) — unchanged.

**CI/scheduled wiring.** ci.yml (every PR): `kill_drill.py --smoke` (1 kill + 1
fork, throwaway temp store, never board/.events.jsonl). recovery-drill.yml (daily
cron + workflow_dispatch): `kill_drill.py --iterations 50` on ubuntu+macos.

**Verify (full suite, from the worktree):** `pytest -q` → 1006 passed, 1 skipped, 0
failed · `diagnostics.py` → 100/100 · `board_lint.py` → 0 · `check_recovery.py`
(default) → exit 0 (inert, contract unchanged) · `ruff check scripts tests` → clean.

**Route to reviewer (CTO):** the shadow-rule ADR supersession that DAS-1445 flagged
(ADR-0010 C3 / ADR-0011 Phase-1 — events becoming load-bearing for operator-invoked
recovery) now has a third participant (`kill_drill.py` in `_EVENT_PRODUCERS`); the
recommended follow-up ADR remains open and is worth a tracked ticket.

### 2026-07-03 — Orchestrator (/daslab-cycle collect)
Done via local-only done-gate: full suite 1020 pass + validators green + merge verification. kill_drill.py: real SIGKILL mid-wave-2 + resume via resume_fork; 20 kill-drills+1 fork-drill -> check_recovery ratio 1.000>=0.99, corrupted 0, zero-lost/zero-dup per-ticket; fork divergence proven. CI smoke + scheduled expensive tier.
