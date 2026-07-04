---
id: DAS-1502
title: Wire wave_runner into daslab-cycle collect as the single mechanical call
status: done
assignee: chairman
author: ceo
dept: engineering
priority: p1
parent: DAS-1497
goal: organism-ws8-attest
depends_on: [DAS-1499]
zone: daslab-cycle
created: 2026-07-03
updated: 2026-07-04
---

## Description

The `/daslab-cycle` wave lifecycle is currently expressed as multi-step PROSE in
`.claude/skills/daslab-cycle/SKILL.md` — a long, LLM-interpreted sequence of
emit/checkpoint/evidence/ledger/guardrail instructions spread across steps
0, 4, 5f, and 6. Every prose step is a compliance surface the orchestrating LLM
can drift on, skip, or reorder. The ORGANISM program's ATTEST phase closes this
by making a ticket's done-ness flow THROUGH an attested runner rather than
through prose the model may or may not honor.

This ticket replaces that prose wave-lifecycle with a SINGLE deterministic call.
At **collect (step 6)**, the orchestrator builds the plan and the results as
DATA (not narration) and calls `scripts/wave_runner.run_wave(plan, results)`
exactly ONCE. That call subsumes the checkpoint/evidence/ledger/guardrail
mechanics that were previously prose, collapsing the LLM-compliance surface from
many steps to one call. Because done-ness now flows through the attested runner,
the runner is structurally load-bearing — not an optional side-effect the model
can bypass.

The call is gated on the `organism_emit` feature flag and is failure-isolated at
the call boundary (a runner error must not crash the wave), BUT the attestation
itself records the success/failure outcome — isolation does not mean silent
swallow. The existing behavior must be preserved bit-for-bit when the flag is
off: the 4 selection guards and the flag-on == flag-off DISPATCH DECISIONS are
invariant (the runner changes attestation/recording, never which tickets get
dispatched).

Extend, don't rewrite: keep the SKILL.md structure and step numbering; surgically
replace the prose lifecycle blocks at steps 0/4/5f/6 with the single-call wiring.
Reuse the existing `scripts/wave_runner.py` API (do not fork a parallel runner).

Key files + paths:
- `.claude/skills/daslab-cycle/SKILL.md` — the prose lifecycle to collapse (steps 0/4/5f/6).
- `scripts/wave_runner.py` — `run_wave(plan, results)`, the attested single entry point.
- `scripts/check_cache_prefix.py` — `CACHE_PREFIX_VERSION` bump + `--fix`.
- `scripts/feature_flags.py` — `organism_emit` gate.
- `scripts/check_loop_mode.py` — skill-token / loop-mode invariant check.

## Acceptance criteria

- [ ] SKILL step-6 collect calls `wave_runner.run_wave(plan, results)` exactly once (prose lifecycle steps 0/4/5f/6 collapsed into the single call).
- [ ] A ticket's done-ness flows THROUGH the attested runner (structurally load-bearing, not an optional side-effect).
- [ ] The call is gated on `organism_emit` and failure-isolated at the call boundary, with the attestation recording success/failure.
- [ ] The 4 selection guards are preserved.
- [ ] flag-on == flag-off DISPATCH DECISIONS (dispatch set unchanged; only attestation/recording differs).
- [ ] `CACHE_PREFIX_VERSION` bumped and `check_cache_prefix --fix` applied.
- [ ] `check_loop_mode` exits 0.
- [ ] `check_cache_prefix` exits 0.
- [ ] Full suite: 0 failed; diagnostics 100/100.

## Log

### 2026-07-03 — CEO
Created from ORGANISM ATTEST-phase decomposition (/daslab-plan, audit-closure). Spec-of-record: docs/research/ORGANISM-PROGRAM-PLAN.md + the closing self-audit.
READ: .claude/skills/daslab-cycle/SKILL.md, scripts/wave_runner.py, scripts/check_cache_prefix.py, scripts/feature_flags.py.
Scope+acceptance (expand; keep frontmatter exact): GATE-5 Deployment. Replace the /daslab-cycle SKILL.md wave-lifecycle PROSE (the multi-step emit/checkpoint/evidence/ledger/guardrail instructions at steps 0/4/5f/6) with a SINGLE deterministic call: at collect (step 6), the orchestrator builds the plan+results as DATA and calls scripts/wave_runner.run_wave(plan, results) ONCE — collapsing the LLM-compliance surface from many prose steps to one call, and making a ticket's done-ness flow THROUGH the attested runner (structurally load-bearing, not optional). Gated on organism_emit; failure-isolated at the call boundary but the attestation records success/failure. Preserve the 4 selection guards + flag-on==flag-off DISPATCH DECISIONS. Bump CACHE_PREFIX_VERSION + check_cache_prefix --fix. Tests/skill-token checks.
Acceptance: [ ] SKILL step-6 collect calls wave_runner.run_wave once (prose lifecycle steps collapsed); [ ] done-ness flows through the attested runner; [ ] 4 guards + flag-on==flag-off decisions preserved; [ ] check_loop_mode + check_cache_prefix exit 0; [ ] full suite 0 failed, diagnostics 100/100.
Constraints: org-engine, NO project: field.

### 2026-07-04 — CTO
Collapsed the /daslab-cycle wave-lifecycle PROSE into the single deterministic
`wave_runner.run_wave(plan, results)` call at collect. Surgically replaced FOUR
prose blocks in `.claude/skills/daslab-cycle/SKILL.md` (structure + step
numbering preserved, extend-not-rewrite):
- **Step 0** — the "Run-model open" multi-sub-step block → a single-call
  description: the whole run-model lifecycle (checkpoints, run_start/run_end/span,
  guardrails, ledgers, evidence, attestation) is performed by ONE `run_wave`
  call at collect; `run_id` now minted at collect, not step 0; failure-isolated
  at the CALL boundary (isolation ≠ silent swallow — WaveAttestation records the
  outcome; CI attestation gate detects a raised load-bearing step).
- **Step 4** — the inline `write_wave_checkpoint` wave-open prose → "capture the
  wave PLAN as DATA"; the checkpoint is now written BY `run_wave` from that plan.
- **Step 5f** — "Run-lifecycle span capture" → "per-dispatch RESULT capture for
  the step-6 runner": buffers ticket/model/role/goal/VERSION/start into the
  `plan`/`results` DATA; no event/checkpoint written here.
- **Step 6** — the ~45-line "Run-lifecycle emission + run close" prose (emit_wave
  + snapshot_evidence + append_ticket_completion + write_wave_checkpoint) → the
  single `run_wave(plan, results)` call, with a REUSE-only code sketch (WavePlan/
  TicketPlan/WaveResults/TicketResult), `organism_emit=enabled(...)` gate, and
  try/except call-boundary isolation. Committed-artifact commit note preserved
  (metrics/evidence + metrics/attestations are TRACKED).

PRESERVED (untouched): step-3 four selection guards (zone / dep-blocked / AADL
gate-order / clarify gate + fanout defer), the step-5d `dgox_emit` shadow block
(separate flag; SHADOW/ADVISORY-ONLY strings kept — test_dgox_phase1_shadow
green), and the flag-on==flag-off DISPATCH DECISIONS invariant (run_wave returns
None + writes nothing when organism_emit off; no dispatch reads events back).

CACHE: bumped CACHE_PREFIX_VERSION v17-stage-gated-delivery → v18-wave-runner-attest
(all four edits are inside the stable-prefix region), ran
`check_cache_prefix.py --fix` in the SAME commit (baseline hash 7a51c2ee → 4c5077aa).

VERIFY (FULL, worktree, LOCAL-only — no push): pytest 1667 passed / 1 skipped (0
failed); diagnostics 100/100; board_lint 0 violations (62 tickets);
`ruff check scripts tests` clean; `check_cache_prefix.py` exit 0;
`check_loop_mode.py` exit 0 (mode shadow, auto_apply false). No library/test code
changed — SKILL prose + baseline only, so the wave_runner unit/e2e suite is
unaffected. NOTE: initial edits landed in the main checkout by mistake; moved to
the worktree and reverted main before committing.

→ in_review. Reviewer = chairman: ROUTING makes CTO's reviewer the CEO, but CEO
authored this ticket, so the board "manager-is-author → one level up" rule (and
the sibling DAS-1498 precedent) routes review to the Chairman — NOT ceo.

### 2026-07-04 — Chairman of the Board
GATE-5 sign-off review (Deployment change to the load-bearing production cycle).
VERDICT: **PASS → done**. Reviewed the merged change (commit d5e1e4e) against the
6 rigor checks; every one holds.

1. **Single-call collapse (steps 0/4/5f/6).** SKILL.md step 6 (the "Wave lifecycle"
   block) issues `wave_runner.run_wave(plan, results)` EXACTLY ONCE, with a
   REUSE-only code sketch (WavePlan/TicketPlan/WaveResults/TicketResult, no
   `dgox.*` import). Step 0 now DESCRIBES the single call (run_id minted at collect,
   not step 0); step 4 only CAPTURES the wave PLAN as DATA ("wave-open checkpoint is
   NO LONGER written here as prose; run_wave writes it"); step 5f only buffers the
   per-dispatch RESULT DATA ("no run_start/run_end/span event ... written here").
   The multi-step emit/checkpoint/evidence/ledger prose is gone from all four steps.
2. **Done-ness flows THROUGH the attested runner.** SKILL asserts it is "structurally
   load-bearing, not an optional side-effect"; confirmed in `scripts/wave_runner.py`
   docstring (lines 446-448): emission (2) and attestation (6) RAISE on failure. The
   `check_attestation.py` CI gate exists and its tests pass (13) — an omission leaves
   no attestation and is detected.
3. **4 step-3 selection guards preserved untouched:** zone/merge_policy correctness
   guard, dep-blocked skip, AADL gate-order (incl. GATE-5 deploy block), and the
   clarify gate + circuit-breaker are all intact in step 3 (plus the fanout `defer`
   double-check). No edit reached the selection logic.
4. **flag-on == flag-off DISPATCH DECISIONS.** `run_wave` is `organism_emit`-gated;
   `wave_runner.py` lines 472-473 return `None` and write nothing when off. The call
   is failure-isolated at the try/except CALL boundary in step 6, and isolation is
   explicitly NOT silent-swallow (load-bearing emission raises inside the call; the
   CI attestation gate surfaces a break). Only post-decision artifacts differ between
   flag states — no dispatch/collect decision reads an event back.
5. **step-5d dgox_emit shadow untouched.** Separate flag ("do NOT conflate the two
   flags"), SHADOW/ADVISORY-ONLY strings intact; `test_dgox_phase1_shadow` green (17).
6. **CACHE_PREFIX_VERSION bumped** v17-stage-gated-delivery → v18-wave-runner-attest;
   `check_cache_prefix.py` exit 0, hash 4c5077aa (matches the CTO's committed baseline).

VERIFY (LOCAL, main checkout): diagnostics 100/100; board_lint 0 violations (62
tickets); pytest 1686 passed / 1 skipped / 0 failed; check_cache_prefix exit 0;
check_loop_mode exit 0 (mode shadow, auto_apply false); test_wave_runner (6) +
test_check_attestation (13) green. No CHANGES requested. Closing to done.
