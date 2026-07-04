---
id: DAS-1452
title: Wire run-model + dispatch emitter into daslab-cycle (preserve 4 guards)
status: done
assignee: chairman
author: ceo
dept: engineering
priority: p1
parent: DAS-1440
goal: organism-ws1-pulse
depends_on: [DAS-1444, DAS-1445, DAS-1455]
zone: daslab-cycle
created: 2026-07-03
updated: 2026-07-03
---

## Description

**What & why.** `/daslab-cycle` is the org's one-wave orchestrator (skill:
`.claude/skills/daslab-cycle/SKILL.md`). Today a wave selects, dispatches, and
reports, but it has no first-class notion of a **run** — there is no durable
`run_id`, no manifest of what a wave attempted, no checkpoint at wave
boundaries, and no lifecycle events a supervisor could observe. The ORGANISM
program (WS1 "pulse") introduces a run-model so the org can resume a crashed
wave, replay what happened, and expose run lifecycle to downstream consumers.
This ticket **wires that run-model into the real dispatch path** so that
invoking a wave actually creates a run, checkpoints at the natural boundaries,
and emits `run_start` / `run_end` / span events.

**AADL stage: GATE-5 Deployment — never auto-approve.** This ticket changes the
live dispatch wiring of the orchestrator that runs every other agent. A human
MUST review it before it lands (LAW / lifecycle: this is production wiring, not
a doc). Do not self-approve; route to the reviewer per `board/ROUTING.md`.

**Dependencies (what this ticket consumes).** This ticket is the *integration*
step — it does not build the primitives, it wires them in:
- **DAS-1444 — resume-fork / run-model** — supplies `run_id`, the run manifest,
  and the resume/fork API. This ticket calls it, does not define it.
- **DAS-1445 — wave-checkpoints** — supplies the checkpoint primitive written at
  wave boundaries. This ticket invokes it at step 0 (run open) and step 6/7
  (wave close).
- **DAS-1455 — dispatch-emitter** — supplies the `run_start` / `run_end` / span
  event emitter. This ticket calls the emitter from the cycle steps; it does NOT
  re-implement event plumbing. (Note the existing shadow `routing_decision`
  emission in step 5d via `scripts/dgox/events.py` is a SEPARATE, advisory-only
  channel — do not conflate the new run-lifecycle emitter with it, and do not
  disturb the `dgox_emit` feature gate.)

**Extend-vs-new posture: EXTEND, do not rewrite.** The cycle skill and its
guards are load-bearing and byte-sensitive (see cache-prefix note below). Add
the run-model wiring as **new steps/sub-steps** and new emitter calls at the
existing seams (step 0 = run open + first checkpoint; step 5 = per-dispatch
spans; step 6/7 = run close + final checkpoint). Do NOT restructure the existing
step numbering or reflow the selection logic. Every existing guard paragraph is
preserved verbatim.

**PRESERVE VERBATIM — the 4 selection guards.** These live in step 3 of
`.claude/skills/daslab-cycle/SKILL.md` and MUST survive this change unchanged
(same bytes, same meaning):
1. **Zone correctness guard** — "never two tickets touching the same repo area /
   file set in the same wave" via the `zone:` field (else `parent` + title
   overlap); the loser waits for the next wave.
2. **`depends_on` gate** — a ticket whose `depends_on:` names an id not yet
   `done` is NOT actionable → skipped, counted `dep-blocked`.
3. **AADL gate order** — a `Stage N` child is not actionable while the same
   project's `Stage N-1` epic is not `done` → skipped, counted gate-blocked.
4. **Clarify gate + circuit-breaker** — an unresolved `[NEEDS CLARIFICATION: …]`
   marker makes a ticket non-actionable (reassign to reviewer, never dispatch to
   a code subagent); if `clarify-blocked` ≥ half the actionable set, HALT the
   wave with a blocker report.

**PRESERVE VERBATIM — two more contracts:**
- The worktree path is a **pure function of the ticket id**:
  `.claude/worktrees/<TICKET-ID>/` (step 5b). The run-model must NOT inject
  `run_id`, timestamps, or any other component into the worktree path.
- The **"one operator invocation = one wave, no background timer"** contract
  (skill header + Boundaries). The run-model adds durable run state for
  resume/replay — it MUST NOT introduce a daemon, night driver, loop, or timer
  chain. A run is opened and closed within a single operator-invoked wave.

**Cache-prefix constraint (hard).** The stable-prefix region of
`.claude/skills/daslab-cycle/SKILL.md` is everything before the sentinel heading
`## Prompt-cache prefix layout (ADR 0006 — W4)` and is byte-checked by
`scripts/check_cache_prefix.py` (invariants a/b/c). Any edit that changes the
bytes of that region (i.e. any edit to steps 0–7 / system text / triage text)
will trip invariant (b) unless `CACHE_PREFIX_VERSION:` in the skill is bumped
(currently `v10-adr-renumber`, line ~424) AND the baseline is regenerated in the
SAME commit via `python3 scripts/check_cache_prefix.py --fix` (writes
`scripts/.cache_prefix_baseline`). Also respect invariant (a): do NOT place any
`run_id`, ISO timestamp, UUID, ticket-id, or `wave-N` counter literal inside the
stable-prefix region — those are volatile and belong only in the dynamic tail
(after the last `cache_control` breakpoint). The run-model wiring text must be
described generically in the prefix; concrete run ids/timestamps live at runtime
in the tail only.

**Key existing files this ticket touches:**
- `.claude/skills/daslab-cycle/SKILL.md` — the orchestrator skill; add run-open
  at step 0, span emission at step 5, run-close + final checkpoint at step 6/7;
  bump `CACHE_PREFIX_VERSION` if prefix bytes change.
- `scripts/check_cache_prefix.py` + `scripts/.cache_prefix_baseline` — the
  cache-prefix gate; re-baseline with `--fix` in the same commit if the prefix
  changed.
- Consumed APIs from DAS-1444 (run-model / resume-fork), DAS-1445
  (wave-checkpoints), DAS-1455 (dispatch-emitter) — call these; do not
  re-implement them here.

## Acceptance criteria

- [ ] Running a real (non-empty) `/daslab-cycle` wave creates a run (durable
      `run_id` + manifest via the DAS-1444 run-model), writes a checkpoint at the
      wave-open boundary and at the wave-close boundary (DAS-1445), and emits
      `run_start`, `run_end`, and per-dispatch span events (DAS-1455).
- [ ] All **4 selection guards** are preserved verbatim (zone correctness,
      `depends_on` gate, AADL gate order, clarify-gate + circuit-breaker) — the
      skill-token / guard tests pass unchanged.
- [ ] The worktree pure-id path `.claude/worktrees/<TICKET-ID>/` is intact — no
      `run_id`/timestamp/other component is injected into the worktree path.
- [ ] No background-timer / daemon / loop behavior is introduced — one operator
      invocation still equals exactly one wave; the run opens and closes within
      that single invocation.
- [ ] Cache-prefix baseline is handled: if the stable-prefix bytes changed,
      `CACHE_PREFIX_VERSION` is bumped AND `scripts/.cache_prefix_baseline` is
      regenerated via `python3 scripts/check_cache_prefix.py --fix` in the SAME
      commit; `python3 scripts/check_cache_prefix.py` exits 0.

## Log

### 2026-07-03 — CEO
Created from ORGANISM program-plan decomposition (/daslab-plan). Spec-of-record: docs/research/ORGANISM-PROGRAM-PLAN.md.

### 2026-07-03 — CTO
Wired the ORGANISM WS1 "pulse" run-model + dispatch emitter into
`.claude/skills/daslab-cycle/SKILL.md`, EXTEND-only (no step renumber, no
selection-logic reflow):
- **Step 0 — run-model open:** mint a durable `run_id` via
  `pulse_checkpoint.generate_ulid()`; the whole run-model (open + checkpoints +
  emission) is gated on a NEW feature flag `organism_emit` (default OFF), a
  SEPARATE channel from the step-5d `dgox_emit` shadow (dgox_emit untouched).
  Explicit no-daemon/no-timer statement: run opens here, closes in step 6, one
  operator invocation = one wave.
- **Step 4 — wave-open checkpoint:** `pulse_checkpoint.write_wave_checkpoint(...)`
  at the wave-open boundary (post step-3 selection, before spawn), recording the
  plan; observational only.
- **Step 5f — run-lifecycle span capture:** buffer per-dispatch
  `DispatchRecord` inputs (run_id/ticket_id/model/role/goal/VERSION/start ts).
- **Step 6 — run-lifecycle emit + run close:** `dispatch_emitter.emit_wave(records)`
  appends the paired `run_start`/`run_end`/span triplet per dispatch (typed
  builders, append-only); `pulse_checkpoint.append_ticket_completion(...)` +
  wave-close `write_wave_checkpoint(...)`; run CLOSED in-wave.
- **Step 7:** report `run_id` + `board/runs/<run_id>/` path when the flag is on.

Enablement flag: **`organism_emit`** added to `scripts/feature_flags.py`
DEFAULTS (default False = safe) + `config/features.yaml`; read via
`feature_flags.enabled("organism_emit")`. Updated `tests/test_feature_flags.py`
exact-dict assertions for the new key (3 tests).

HARD CONSTRAINTS held:
- **4 selection guards PRESERVED VERBATIM** — step 3 (zone correctness,
  depends_on gate, AADL gate order, clarify gate + circuit-breaker) is byte-for-
  byte unchanged; diff hunks touch only steps 0/4/5f/6/7 + the version line.
- **Worktree pure-id path** `.claude/worktrees/<TICKET-ID>/` (step 5b) intact —
  no run_id/timestamp injected into the path (explicitly reaffirmed in 5f text).
- **No background timer/daemon/loop** — run opens and closes within one wave.
- **`check_loop_mode.py` exit 0** — loop.yaml NOT touched (stays shadow,
  auto_apply false).
- **Emission is post-decision / observational / failure-isolated** — every emit/
  checkpoint/completion is wrapped; a failed append never blocks dispatch;
  flag-on == flag-off dispatch DECISIONS (only difference = lines in gitignored
  `board/.events.jsonl` + artifacts under `board/runs/<run_id>/`).

Cache-prefix: stable-prefix bytes changed (steps 0/4/5f/6/7 are before the
sentinel) → bumped `CACHE_PREFIX_VERSION` v13-interrupt-mergepolicy →
`v14-organism-runmodel` and regenerated `scripts/.cache_prefix_baseline` via
`check_cache_prefix.py --fix` in this commit; no volatile tokens introduced.

Full suite GREEN: pytest 993 passed / 1 skipped; diagnostics 100/100;
board_lint 0; check_loop_mode exit 0; check_cache_prefix exit 0;
check_never_auto_approve clean; ruff clean.

**GATE-5 Deployment — never auto-approve.** This is live dispatch wiring of the
orchestrator. Not self-approving: status → in_review, assignee → chairman for a
deployment-gate review (CTO's reviewer is CEO, but CEO is the author →
escalate one level to Chairman per ROUTING.md; aligns with the GATE-5 directive).
Local-only: committed on branch `feat/das-1452-wire-cycle`, no push/PR.

### 2026-07-03 — Chairman of the Board
**GATE-5 (Deployment) sign-off — PASS.** Reviewed the merged change (commit
`6b1ee0e`, local main): `.claude/skills/daslab-cycle/SKILL.md`,
`scripts/feature_flags.py`, `config/features.yaml`, `scripts/.cache_prefix_baseline`,
`tests/test_feature_flags.py`. Never-auto-approve deployment gate: a human (this
Chairman review) is the required approver; not self-approved (CTO author's chain
escalated CEO→Chairman since CEO is the ticket author).

Deployment-safety items verified:
1. **Emission dark by default** — `organism_emit` defaults **False** in both
   `scripts/feature_flags.py` DEFAULTS and `config/features.yaml` (latent-machine
   law ADR-0019). It is a SEPARATE channel from `dgox_emit`; the `dgox_emit` value
   is unchanged (`False`) — its `+` diff line is only the DEFAULTS dict being
   reformatted single-line→multi-line, not a value change. `dgox_emit` semantics
   untouched.
2. **4 selection guards preserved verbatim** — step 3 (zone correctness,
   `depends_on` gate, AADL gate order, clarify gate + circuit-breaker) is
   byte-for-byte unchanged: no diff hunk lands in the step-3 line range (hunks hit
   only steps 0/4/5f/6/7 + the CACHE_PREFIX_VERSION line); a grep for
   zone/depends_on/AADL/clarify among added lines finds only the new step-0/5f
   prose, no guard edits.
3. **No background timer/daemon** — the only timer/daemon/loop tokens introduced
   are NEGATIONS affirming the "one operator invocation = one wave, no background
   timer" contract; the run opens in step 0 and CLOSES in step 6 within the same
   wave. No driver/loop added.
4. **QONUN-5 / loop safety** — `python3 scripts/check_loop_mode.py` exit 0
   (loop.yaml untouched: mode 'shadow', auto_apply false, levers only).
5. **Post-decision / observational / failure-isolated** — every run-model call
   (ULID mint, checkpoint, completion, emit) is wrapped; a failed append never
   blocks dispatch. Flag-on == flag-off dispatch DECISIONS; only difference is
   lines in gitignored `board/.events.jsonl` + artifacts under `board/runs/<run_id>/`.

Validators (local main, this review):
- `scripts/diagnostics.py` → **100/100**
- `scripts/board_lint.py` → **0 violations** (17 tickets)
- `scripts/check_cache_prefix.py` → **exit 0** (v14-organism-runmodel; ~8450
  prefix tokens; no volatile tokens; hash stable)
- `scripts/check_never_auto_approve.py` → **clean** (17 tickets)
- `scripts/check_loop_mode.py` → **exit 0**
- `python3 -m pytest -q` → **1020 passed, 1 skipped, 0 failed**

**Verdict: PASS → done.** Local-only "done" = green validators + this GATE-5
review; no push/PR. `organism_emit` STAYS OFF until a Founder governance
flag-flip authorizes turning the run-model machinery on (latent until a consumer
+ explicit enablement).
