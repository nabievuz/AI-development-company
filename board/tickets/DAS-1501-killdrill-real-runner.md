---
id: DAS-1501
title: Retrofit kill-drill to exercise the real wave_runner
status: done
assignee: cto
author: ceo
dept: engineering
priority: p1
parent: DAS-1497
goal: organism-ws8-attest
depends_on: [DAS-1499]
zone: recovery-drill
created: 2026-07-03
updated: 2026-07-04
---

## Description

GATE-4. The closing self-audit of the ORGANISM ATTEST phase found that the
kill-drill (`scripts/kill_drill.py`) uses a hand-rolled synthetic dispatcher.
This proves the recovery PRIMITIVES (checkpoints, resume-fork, event log)
survive a crash, but it does NOT exercise the production wave lifecycle — the
same code path production actually runs. A drill that bypasses the real runner
can pass while the real runner has a latent crash-recovery bug.

Retrofit `scripts/kill_drill.py` so its 3-wave synthetic run drives waves
THROUGH the real `scripts/wave_runner.run_wave` (the deterministic lifecycle
production uses), then `kill -9` mid-wave-2 and resume via
`scripts/resume_fork.py`. This proves the ACTUAL wave-runner lifecycle
(events + checkpoints + attestation) survives a real SIGKILL with zero
lost/dup work items and a valid resumed attestation chain — not just the
primitives in isolation.

Extend-vs-new: EXTEND the existing `scripts/kill_drill.py` and its
`check_recovery` scoring; do not fork a parallel drill. Keep the T5 >= 0.99
threshold and the current scoring semantics intact.

Key files/paths:
- `scripts/kill_drill.py` — the drill to retrofit (replace the hand-rolled
  dispatcher with real `wave_runner.run_wave` calls)
- `scripts/wave_runner.py` — `run_wave` is the real lifecycle to drive through
- `scripts/resume_fork.py` — resume path after the SIGKILL
- `scripts/pulse_checkpoint.py` — checkpoint primitive the lifecycle uses
- the kill-drill's own tests (update to cover the real-runner path)

## Acceptance criteria

- [ ] kill-drill drives waves through the real `wave_runner.run_wave` (not a
      hand-rolled dispatcher)
- [ ] real SIGKILL mid-wave-2 + resume via `resume_fork`: zero lost/dup work
      items, resumed attestation chain valid, T5 >= 0.99
- [ ] existing `check_recovery` scoring preserved (T5 >= 0.99 threshold kept)
- [ ] kill-drill tests updated to cover the real-runner path
- [ ] full suite 0 failed, diagnostics 100/100

## Log

### 2026-07-04 — QA Lead
Retrofitted `scripts/kill_drill.py` so the 3-wave synthetic run drives every wave
THROUGH the real `wave_runner.run_wave` — the deterministic production lifecycle
(open/close checkpoints, run_start/run_end/span events, per-ticket completions,
committed evidence, doubly hash-chained `WaveAttestation` per wave). The
hand-rolled synthetic dispatcher is gone: no more `build_routing_decision`
transitions or `write_wave_checkpoint` calls in the drill (asserted by a test).

- Each wave gets its own `run_id` so the attestations form a wave-to-wave hash
  chain (`attest_chain.prev` → prior wave's `self`).
- The child now `kill -9`s itself DEEP INSIDE `run_wave` mid-wave-2 (via a hook on
  `pulse_checkpoint.append_ticket_completion`) — right after the wave's first
  ticket completion is fsync'd but BEFORE the wave-2 checkpoint/evidence/
  attestation commit. A genuine abrupt death mid-lifecycle.
- Resume via `resume_fork`: a wave with a committed, verifying attestation is
  done; any other wave is re-driven through `run_wave` for EXACTLY the tickets
  lacking a durable completion record. `resume_fork.resume_run` enforces the T5
  zero-corrupted guardrail; the completion records are the durable work-item
  ledger. A ticket completed before the crash is never re-dispatched
  (guard-before-act) — verified: DAS-8001/8002/8003 not in the resume set.
- Proven across the crash boundary: zero lost, zero duplicated, and a VALID
  resumed attestation chain (every wave attestation verifies + links to its
  predecessor, including the resumed wave-2 and wave-3). Fork drill likewise
  driven through `run_wave` (base 2-wave single-`run_id` so the checkpoint
  delta-chain reconstructs; fork diverges done→blocked; base intact).
- Kept the T5 >= 0.99 threshold + existing `check_recovery` scoring + the exact
  `recovery_drill` emission shape untouched.
- Note for reviewer: `run_wave` resolves its guardrails-dir default eagerly to a
  non-existent `_gd.DEFAULT_GUARDRAILS_DIR`, so any caller not passing
  `guardrails_dir` (even with `run_guardrails=False`) hits an AttributeError. The
  drill works around it by passing a hermetic `guardrails_dir` (never read on the
  off path). This is a latent `wave_runner.py` bug (different zone, not touched
  here) — flagging for a possible follow-up fix.

VERIFY (FULL, local worktree): `python3 -m pytest -q` → 1672 passed, 1 skipped,
0 failed; `python3 scripts/diagnostics.py` → 100/100; `python3
scripts/board_lint.py` → 0 violations; `ruff check scripts tests` → clean;
`python3 scripts/kill_drill.py --smoke` → exit 0. Committed LOCAL-ONLY (no push).
Status → in_review, assignee → CTO (reviewer per ROUTING).

### 2026-07-03 — CEO
Created from ORGANISM ATTEST-phase decomposition (/daslab-plan, audit-closure).
Spec-of-record: `docs/research/ORGANISM-PROGRAM-PLAN.md` + the closing
self-audit. READ: `scripts/kill_drill.py`, `scripts/wave_runner.py`,
`scripts/resume_fork.py`, `scripts/pulse_checkpoint.py`. The self-audit found
the kill-drill uses a hand-rolled synthetic dispatcher, so it proves the
PRIMITIVES survive a crash but NOT the production lifecycle. Retrofit so the
3-wave synthetic run drives waves through the real `wave_runner.run_wave`,
then `kill -9` mid-wave-2 and resume via `resume_fork` — proving the actual
wave-runner lifecycle (events + checkpoints + attestation) survives a real
SIGKILL with zero lost/dup and a valid resumed attestation chain. Keep
T5 >= 0.99 + the existing `check_recovery` scoring. Tests updated.

### 2026-07-03 — Orchestrator (/daslab-cycle collect)
Done via local-only done-gate: full suite 1686; kill_drill now drives its 3-wave run THROUGH the real wave_runner.run_wave (production lifecycle, not a hand-rolled dispatcher); kill -9 deep inside run_wave mid-wave-2, resume via resume_fork -> zero lost/dup, valid resumed attestation chain, T5>=0.99. Flagged the wave_runner guardrails_dir default AttributeError (now fixed + regression-tested). 18 tests.
