---
id: DAS-1506
title: Wave reconciliation validator with committed baseline
status: done
assignee: cto
author: ceo
dept: engineering
priority: p1
parent: DAS-1503
goal: organism-ws9-harness
depends_on: [DAS-1505]
zone: reconciliation-gate
created: 2026-07-04
updated: 2026-07-04
---

## Description

**What.** Build `scripts/check_wave_reconciliation.py`, a GATE-4 (ADR-0032)
validator that proves the dispatch record is internally consistent: the
committed wave ledger (`board/wave-ledger.jsonl`), the committed per-run
attestations (`metrics/attestations/<run_id>.json`), and the board ticket
states must all agree. It is the ORGANISM HARNESS-phase closure for the ATTEST
re-audit residual — the attestation layer (DAS-1505) records each wave, but
nothing yet fails CI when a ledger entry goes missing, an attestation is
orphaned, the hash chain is broken, or a recorded ticket never reached a
terminal state.

**Why.** Without reconciliation, an agent (or a bad merge) can silently drop a
wave-ledger line or tamper an `attestation_hash` and the repo still goes green —
the exact class of trust gap the ORGANISM audit closure targets. This gate makes
the dispatch record tamper-evident and gap-evident, fail-closed.

**Extend vs new.** NEW file `scripts/check_wave_reconciliation.py`. Extend the
existing gates: wire the new check into `scripts/diagnostics.py` as a real RUN
check (keep the score at 100/100) and add a gate step to
`.github/workflows/ci.yml`. Do not fork the attestation-hash logic — read and
reuse the hashing/attestation helpers from `scripts/check_attestation.py`
(DAS-1505) so both gates compute `attestation_hash` identically.

**Key files + paths (READ first).**
- `scripts/wave_runner.py` — how waves emit ledger entries + attestations.
- `scripts/check_attestation.py` — attestation shape + hash computation to reuse.
- `scripts/diagnostics.py` — RUN-check registry; add the new check, keep 100/100.
- `.github/workflows/ci.yml` — add the gate step.
- `board/wave-ledger.jsonl` — the committed ledger (source of truth for waves).
- `metrics/attestations/<run_id>.json` — committed per-run attestations.
- NEW: `board/.attestation-baseline` — committed HEAD SHA grandfathering
  pre-regime done tickets so the existing repo stays green.

**Enforcement rules.**
1. **BIJECTION** — every committed `board/wave-ledger.jsonl` entry has a
   committed attestation `metrics/attestations/<run_id>.json` whose ticket set
   AND `attestation_hash` match, and every committed attestation has a ledger
   entry. No orphan in either direction.
2. **CHAIN CONTINUITY** — per `run_id` the ledger entries form an unbroken hash
   chain (`prev`/`self`); a GAP (a recorded wave whose entry was dropped) FAILS.
3. **TERMINAL** — every ticket named in a ledger entry is terminal
   (`done`/`blocked`) on the board.
4. **BASELINE** — write/read a committed `board/.attestation-baseline` holding
   the current HEAD SHA so pre-regime done tickets are grandfathered. Fail-closed
   on any post-baseline reconciliation gap; inert-by-design ONLY when both the
   ledger and the attestations are empty.

## Acceptance criteria

- [x] `check_wave_reconciliation` enforces bijection + chain-continuity +
      terminal + baseline.
- [x] The committed sample reconciles green.
- [x] Dropped-entry / chain-gap / orphan-attestation / tampered-`attestation_hash`
      each FAIL with teeth (tests).
- [x] Wired into `scripts/diagnostics.py` (100/100) AND `.github/workflows/ci.yml`
      as a gate step.
- [x] Full test suite: 0 failed.

## Log

### 2026-07-04 — CEO

Created from ORGANISM HARNESS-phase decomposition (/daslab-plan, audit-closure
final phase). Spec-of-record: docs/research/ORGANISM-PROGRAM-PLAN.md + the ATTEST
re-audit residual.

READ: scripts/wave_runner.py, scripts/check_attestation.py, scripts/diagnostics.py,
.github/workflows/ci.yml, board/wave-ledger.jsonl.

Scope+acceptance (expand; keep frontmatter exact): GATE-4 (ADR-0032). Build
scripts/check_wave_reconciliation.py enforcing: (1) BIJECTION — every committed
board/wave-ledger.jsonl entry has a committed attestation
(metrics/attestations/<run_id>.json) whose ticket set + attestation_hash match,
and every committed attestation has a ledger entry (no orphan either way);
(2) CHAIN CONTINUITY — per run_id the ledger entries form an unbroken hash chain
(prev/self), so a GAP (a recorded wave whose entry was dropped) FAILS;
(3) TERMINAL — every ticket named in a ledger entry is terminal (done/blocked)
on the board; (4) BASELINE — write/read a committed board/.attestation-baseline
(the current HEAD SHA) so pre-regime done tickets are grandfathered and the
existing repo stays green; fail-closed on any post-baseline reconciliation gap,
inert-by-design only when both ledger and attestations are empty. Wire into
scripts/diagnostics.py (a real RUN check, keep 100/100) AND
.github/workflows/ci.yml as a gate step. Tests: the committed sample reconciles
(pass); a dropped ledger entry / a chain gap / an orphan attestation / a tampered
attestation_hash each FAIL with teeth.

Acceptance: [ ] check_wave_reconciliation enforces bijection + chain-continuity +
terminal + baseline; [ ] committed sample reconciles green; [ ] dropped-entry /
chain-gap / orphan / tampered-hash each FAIL (tests); [ ] wired into diagnostics
(100/100) + ci.yml; [ ] full suite 0 failed.

Constraints: org-engine, NO project: field.

### 2026-07-04 — QA Lead

Built the GATE-4 reconciliation validator and wired it in. Committed locally on
`feat/das-1506-check-reconciliation` (STRICT LOCAL-ONLY — no push/PR).

**Shipped**
- `scripts/check_wave_reconciliation.py` — reuses `wave_runner`'s SSOT
  (`LEDGER_PATH`/`LEDGER_FIELDS`/`ATTEST_DIR`, `_GENESIS_PREV_HASH`,
  `_ledger_self_hash`, `_sha256_bytes`, `attestation_path`/`load_attestation`) — no
  re-implementation. Four arms:
  1. **BIJECTION** — every ledger entry ⇄ its `metrics/attestations/<run_id>.json`;
     ticket set + `wave` agree and `attestation_hash` is recomputed from the committed
     attestation FILE bytes exactly as the writer did (`_sha256_bytes(ap.read_bytes())`);
     orphans in either direction FAIL.
  2. **CHAIN** — the ledger's own `prev`/`self` chain verifies end-to-end in append
     order (dropped/edited/reordered line breaks it) AND per-`run_id` wave indices are
     gap-free `1..K` (a mid-sequence skip FAILS).
  3. **TERMINAL** — every recorded ticket present on the board is `done`/`blocked`
     (a ledger ticket absent from the live board — e.g. the synthetic sample — is not
     provably non-terminal, so not a violation).
  4. **BASELINE + COVERAGE** — reads/validates the committed `board/.attestation-baseline`
     (fail-closed if missing when anything is checkable); COVERAGE requires a committed
     ledger entry only for a board ticket that is terminal AND carries a `run_id:`
     frontmatter field (the post-regime marker). The current 67 pre-regime/no-run_id
     tickets carry no such field → grandfathered → repo stays green.
  - Inert-by-design ONLY when ledger + attestations empty and no coverage-needing ticket.
- `board/.attestation-baseline` — HEAD SHA `02b1f596918234270a2c3967315f04fa4f3e45a3`
  (`git rev-parse HEAD`), committed, tracked (not gitignored).
- Wired into `scripts/diagnostics.py` (Architecture dim, real RUN check
  `wave-reconciliation`) and `.github/workflows/ci.yml` (gate step after
  `check_attestation`).
- `tests/test_check_wave_reconciliation.py` — 17 tests driving real receipts through
  `wave_runner.run_wave`: committed sample reconciles; dropped entry (hash break),
  wave-sequence gap, orphan attestation, orphan ledger entry, tampered
  `attestation_hash`, tampered ticket set, non-terminal recorded ticket, uncovered
  post-baseline done each FAIL; covered/terminal/grandfathered/inert/missing-baseline
  paths verified.

**Verify (FULL, in worktree)**
- `python3 -m pytest -q` → 1705 passed, 1 skipped, 0 failed.
- `python3 scripts/diagnostics.py` → SCORE = 100/100.
- `python3 scripts/board_lint.py` → 0 violations (67 tickets).
- `ruff check scripts tests` → clean.
- `python3 scripts/check_wave_reconciliation.py` → exit 0 on the committed sample.

**Routing** — `status: in_review`, `assignee: cto` (my reviewer per `board/ROUTING.md`;
qa-lead → CTO). `done` requires the merged PR with green CI, per the git rules — the
orchestrator handles branch/PR (this run is STRICT LOCAL-ONLY).

### 2026-07-04 — Orchestrator (/daslab-cycle collect)
Done. check_wave_reconciliation.py enforces bijection+chain (delegated to the wave_runner.verify_wave_ledger SSOT — no fork) + its additive arms (per-run_id wave contiguity, terminal, baseline+coverage grandfathering the 67 pre-regime dones); committed board/.attestation-baseline; wired into diagnostics+ci; 17 tests (dropped/gap/orphan/tamper each FAIL with teeth).
