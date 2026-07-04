---
id: DAS-1507
title: Wire wave-ledger into cycle and prove chain survives a crash
status: done
assignee: chairman
author: ceo
dept: engineering
priority: p1
parent: DAS-1503
goal: organism-ws9-harness
depends_on: [DAS-1505]
zone: daslab-cycle
created: 2026-07-04
updated: 2026-07-04
---

## Description

**What / why.** The ORGANISM HARNESS phase closes the audit-loop by making a
wave leave a durable, tamper-evident trace. DAS-1505 lands the committed
wave-ledger primitive (an append-only, hash-chained record co-produced with
each `run_wave` call). This ticket wires that primitive into the actual
run path — the `/daslab-cycle` skill — and hardens it against process death:
the ledger must be the durable "a wave happened" record so that a dropped or
omitted wave is *detectable* rather than silently lost, and the chain must
survive a real crash without a gap or a duplicate.

This is a GATE-5 (Deployment) item: it changes how the org actually runs a
wave in production and proves the runtime survives a crash+resume.

**Embedded context.** Spec-of-record is
`docs/research/ORGANISM-PROGRAM-PLAN.md` plus the ATTEST re-audit residual
(the reconciliation-at-collect-time requirement, T5 attestation coverage
threshold >= 0.99). The wave-ledger is co-produced by the single `run_wave`
call already documented in the skill's step 6; here we (a) document the
co-production + collect-time reconciliation in the skill and (b) prove the
chain survives SIGKILL in the kill-drill.

**Extend vs new.** EXTEND existing artifacts — do NOT introduce new scripts or
a parallel run path:
- Extend the prose of `.claude/skills/daslab-cycle/SKILL.md` step 6 (single
  `run_wave` call stays single; add the ledger + reconciliation documentation).
- Extend `scripts/kill_drill.py` with a crash+resume assertion over the
  committed wave-ledger chain.
- Reuse the reconciliation check produced/wired by DAS-1505
  (`check_wave_reconciliation`) rather than writing a new reconciler.

**Key files + paths.**
- `.claude/skills/daslab-cycle/SKILL.md` — step 6 (the single `run_wave`
  call; the 4 selection guards; the flag-on == flag-off DISPATCH DECISIONS
  invariant).
- `scripts/wave_runner.py` — the `run_wave` implementation that co-produces
  the ledger.
- `scripts/kill_drill.py` — crash+resume drill to extend.
- `scripts/check_cache_prefix.py` — `CACHE_PREFIX_VERSION` (currently v18);
  bump + `--fix` in the same commit.

## Acceptance criteria

- [ ] `.claude/skills/daslab-cycle/SKILL.md` step 6 documents the committed
      wave-ledger co-production AND the collect-time reconciliation
      (`check_wave_reconciliation` run after the wave), noting the ledger is
      the durable "a wave happened" record that makes omission detectable.
- [ ] The single `run_wave` call in step 6 stays single; the 4 selection
      guards and the flag-on == flag-off DISPATCH DECISIONS invariant are
      preserved.
- [ ] `CACHE_PREFIX_VERSION` bumped (v18 → next) and `check_cache_prefix.py
      --fix` run in the same commit; `python3 scripts/check_cache_prefix.py`
      exits 0.
- [ ] `scripts/kill_drill.py` proves the committed wave-ledger chain survives
      a real SIGKILL mid-wave: after kill + resume, the ledger is a valid
      unbroken chain with no gap and no duplicate, and reconciles against the
      attestations (T5 coverage >= 0.99 preserved).
- [ ] Tests added/extended for the above.
- [ ] Full suite: 0 failed; diagnostics 100/100.

## Log

### 2026-07-04 — CEO
Created from ORGANISM HARNESS-phase decomposition (/daslab-plan, audit-closure final phase). Spec-of-record: docs/research/ORGANISM-PROGRAM-PLAN.md + the ATTEST re-audit residual.
READ: .claude/skills/daslab-cycle/SKILL.md, scripts/wave_runner.py, scripts/kill_drill.py, scripts/check_cache_prefix.py.
Scope+acceptance (expand; keep frontmatter exact): GATE-5 Deployment. (a) Update .claude/skills/daslab-cycle/SKILL.md step 6 so the single run_wave call now also documents the committed wave-ledger co-production + the collect-time reconciliation (run check_wave_reconciliation after the wave), noting the ledger is the durable 'a wave happened' record that makes omission detectable. Preserve the 4 selection guards + flag-on==flag-off DISPATCH DECISIONS. Bump CACHE_PREFIX_VERSION (currently v18) + check_cache_prefix --fix same commit. (b) Extend scripts/kill_drill.py so its crash+resume proves the committed wave-ledger CHAIN survives a real SIGKILL: after kill mid-wave + resume, the wave-ledger is a valid unbroken chain with no gap or duplicate and reconciles against the attestations (T5>=0.99 preserved). Tests.
Acceptance: [ ] SKILL step 6 documents the committed wave-ledger + collect-time reconciliation; [ ] 4 guards + flag-on==flag-off preserved; [ ] cache bumped + check_cache_prefix exit 0; [ ] kill-drill proves the wave-ledger chain survives a SIGKILL (no gap/dup, reconciles) w/ T5>=0.99; [ ] full suite 0 failed, diagnostics 100/100.
Constraints: org-engine, NO project: field. Do not create any other file. Do not run git. Return only "DAS-1507 written".

### 2026-07-04 — CTO

GATE-5 Deployment implementation complete; status todo → in_review. LOCAL-ONLY
(no push/PR per dispatch directive). Branch feat/das-1507-harness-skill-killdrill.

(a) **SKILL.md step 6** — documented, in the single `run_wave` collect call, the
committed wave-ledger co-production (append-only, hash-chained
`board/wave-ledger.jsonl`, ATOMIC with the attestation per ADR-0032 §1) as the
durable "a wave happened" record that makes an omitted wave *detectable* rather
than silently lost (a wave that commits done-ness MUST leave a reconciled ledger
entry). Added the collect-time reconciliation step: run
`scripts/check_wave_reconciliation.py` after the wave (bijection + chain-continuity
+ terminal), noting it reads through the same `wave_runner` SSOT the runner writes
with. PRESERVED: the single `run_wave` call stays single; the 4 selection guards
(step 3) untouched; the flag-on == flag-off DISPATCH DECISIONS invariant restated
(flag-off ⇒ no attestation AND no ledger line; the only flag-state delta is
post-decision artifacts). Bumped `CACHE_PREFIX_VERSION` v18 → v19-wave-ledger-reconcile
and ran `check_cache_prefix.py --fix` in the same commit (exit 0, no volatile
tokens, ~10534-token stable prefix).

(b) **kill_drill.py** — the crash+resume drill now proves the committed
wave-ledger CHAIN survives a real SIGKILL: after kill mid-wave-2 + resume, the
hermetic drill ledger is a valid unbroken chain with NO gap and NO duplicate that
reconciles against the attestations, verified THROUGH the new SSOT
`wave_runner.verify_wave_ledger`. `run_kill_drill` returns `ledger_reconciles` /
`ledger_problems` / `ledger_path`; folded into `ok` and into the `recovery_drill`
`corrupted` verdict, so a broken/unreconciled ledger → corrupted=true → the T5
zero-corrupted guardrail FAILs. T5 >= 0.99 preserved (smoke: 1.000, corrupted 0).

**Design note / cross-ticket flag:** the reconciliation SSOT
`verify_wave_ledger(ledger_path, *, attest_dir, reconcile_attestations)` was added
to `scripts/wave_runner.py` (the module that already owns `LEDGER_FIELDS` + the
ledger hashing) rather than to `scripts/check_wave_reconciliation.py`, because that
CLI gate (DAS-1506) is still `todo` and is NOT a dependency of DAS-1507
(`depends_on: [DAS-1505]`). The ticket text attributed the reconciler to DAS-1505,
but it is actually DAS-1506's deliverable. Placing the canonical bijection +
chain-continuity primitive in `wave_runner` gives ONE SSOT that DAS-1506's CLI
should WRAP (not fork) — consistent with ADR-0032 §1 (`LEDGER_FIELDS` is the
"single SSOT the reconciliation validator reuses"). ROUTE: DAS-1506 (qa-lead)
should build `check_wave_reconciliation.py` on top of `wave_runner.verify_wave_ledger`
+ add the board-terminal and `board/.attestation-baseline` grandfathering it owns.

VERIFY (FULL, in worktree): `pytest -q` 1698 passed / 1 skipped / 0 failed;
`diagnostics.py` 100/100; `board_lint.py` 0 violations; `ruff check scripts tests`
clean; `check_loop_mode.py` exit 0; `check_cache_prefix.py` exit 0;
`kill_drill.py --smoke` exit 0 (T5 1.000, corrupted 0).

Reviewer: assignee → chairman (CEO is the ticket author, so the CTO→CEO reviewer
edge escalates one level up per ROUTING's manager-is-author rule).

### 2026-07-04 — Chairman of the Board

GATE-5 (Deployment) sign-off — **VERDICT: PASS**. This change alters how the org
actually runs a wave in production (the committed wave-ledger co-production +
collect-time reconciliation) and proves the runtime survives crash+resume.
Reviewed the merged state on `main` (5069d0c); LOCAL-ONLY, no remote contact.

**Verified against all four acceptance criteria:**

1. **SKILL.md step 6 — committed wave-ledger + collect-time reconciliation, with
   the single `run_wave` call and all invariants preserved.** Step 6 (lines
   553–652) documents the co-produced, append-only, hash-chained
   `board/wave-ledger.jsonl` as the durable "a wave happened" record that makes an
   omitted/tampered wave *detectable* (breaks a committed chain) rather than
   silently lost, plus the collect-time gate `check_wave_reconciliation.py` run
   after the wave. The `run_wave` call stays SINGLE (called EXACTLY ONCE). The 4
   selection guards (zone, dep-blocked, AADL gate-order, clarify gate) are intact
   (SKILL line 775). **flag-on == flag-off DISPATCH DECISIONS holds and is
   correct in code:** `wave_runner.run_wave` returns `None` before ANY side effect
   when `organism_emit` is off (lines 752–753), and the SKILL restates flag-off ⇒
   no attestation AND no wave-ledger line (lines 630–631). No dispatch/collect
   decision reads an emitted event back.

2. **`wave_runner.verify_wave_ledger` is a clean SSOT reconciler, exported, reused
   by kill_drill.** In `__all__`; implements well-formed (exactly `LEDGER_FIELDS`)
   + no-duplicate `(run_id, wave)` + chain-continuity (genesis-anchored append
   chain; dropped line ⇒ gap, tampered ⇒ break) + bijection (each entry ↔ a
   verifying committed attestation with matching hash/tickets/wave; no orphan
   attestation). Empty/absent ledger is inert-by-design. `kill_drill.py`
   reconciles THROUGH it (line 435).

3. **Ledger chain survives a real SIGKILL — proven.** `kill_drill.py --smoke`
   exit 0: `killed=True zero_lost=True zero_dup=True chain_clean=True
   ledger_reconciles=True`; **T5 recovery 1.000 (≥ 0.99), corrupted 0**. A broken/
   dropped/tampered/orphaned ledger folds into `corrupted` → the T5 zero-corrupted
   guardrail FAILs (kill_drill lines 441–445). Negative tests confirm teeth:
   `test_kill_drill.py::test_a_dropped_ledger_line_is_caught_by_the_gate`, plus
   `test_wave_runner.py` covers dropped-line-as-chain-gap, tampered
   attestation_hash, duplicate, and orphan attestation.

4. **`CACHE_PREFIX_VERSION` bumped v18 → v19-wave-ledger-reconcile;
   `check_cache_prefix.py` exit 0** (~10534-token stable prefix, no volatile
   tokens, hash stable).

**Design decision confirmed SOUND (the builder's cross-ticket flag).** Placing
`verify_wave_ledger` in `wave_runner.py` — beside `LEDGER_FIELDS` and the ledger
hashing (`_ledger_self_hash`, `_GENESIS_PREV_HASH`) that write the chain — is the
correct SSOT location: the reconciler lives WITH the writer, so there is ONE
place the ledger's integrity is decided and both `kill_drill` and DAS-1506's CLI
gate reuse it rather than forking. This matches ADR-0032 §1 (`LEDGER_FIELDS` = the
single SSOT the reconciliation validator reuses). SSOT with the writer, not a fork
— sound.

**Non-blocking observation (out of DAS-1507 scope):** the SKILL prose says
`check_wave_reconciliation` "reads the ledger through the same wave_runner SSOT
primitive (verify_wave_ledger)"; DAS-1506's already-merged CLI actually reuses
`wave_runner`'s constituent SSOT primitives (`_ledger_self_hash`,
`_GENESIS_PREV_HASH`, `LEDGER_FIELDS`, `attestation_path`, `_sha256_bytes`) with
its own loop rather than calling the top-level `verify_wave_ledger`. The
substantive claim ("never forks the chain/hash logic") is TRUE — the chain/hash
SSOT is genuinely reused. This is a cosmetic prose nuance in a separately-merged
ticket (DAS-1506, GATE-4), not a DAS-1507 defect; noted for a future doc
touch-up, does not block GATE-5.

**Full verification suite (local, on `main`):** `diagnostics.py` **100/100**;
`board_lint.py` **0 violations** (67 tickets); `pytest -q` **1715 passed / 1
skipped / 0 failed**; `check_cache_prefix.py` **exit 0**; `check_loop_mode.py`
**exit 0** (loop off, shadow mode); `kill_drill.py --smoke` **exit 0** (T5 1.000,
corrupted 0).

status: in_review → **done**. GATE-5 signed off.
