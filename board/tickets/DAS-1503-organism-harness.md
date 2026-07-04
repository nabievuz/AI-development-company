---
id: DAS-1503
title: ORGANISM — HARNESS (harness-forced wave attestation)
status: done
assignee: cto
author: ceo
dept: engineering
priority: p1
parent: 
goal: organism-ws9-harness
created: 2026-07-04
updated: 2026-07-04
---

## Description

**What.** Close the ORGANISM audit by making the wave-attestation regime
HARNESS-FORCED. Today `run_wave` (scripts/wave_runner.py) writes an attestation
that `scripts/check_attestation.py` verifies, and ADR-0031 records the design.
The ATTEST phase (WS8) already made *partial* or *tampered* wave emission
CI-detectable. But the re-audit surfaced the IRREDUCIBLE residual: a **TOTAL
silent omission** — the orchestrator LLM simply never calls `run_wave` — leaves
no committed trace at all, and `check_attestation` is inert on an empty store,
so CI passes green over a wave that never happened.

**Why.** An LLM-driven orchestrator cannot be forced to emit a record by pure
runtime assertion; the only durable teeth come from a *committed* artifact whose
absence or discontinuity is itself detectable. This phase closes as much of the
residual as an LLM-driven runtime allows by co-producing a **committed,
hash-chained wave-ledger** atomically with each attestation, plus a
**reconciliation validator** that enforces a bijection (ledger entries ↔
attestations) and chain-continuity in CI and diagnostics. Any recorded wave that
is skipped mid-sequence, tampered with, or left unattested then BREAKS the
durable committed hash-chain → CI fails with teeth. A committed baseline
grandfathers the pre-regime done tickets so the existing repo stays green.

The honest floor remains and MUST be recorded in the ADR: a wave that does zero
committed work still leaves nothing to chain — but it also delivered nothing, so
the residual is bounded to the empty set of real outcomes.

**Extend vs new.** EXTEND — this is the final (WS9 / audit-closure) phase built
on the existing attestation machinery. Extend `scripts/wave_runner.py` (ledger
co-production, atomic with attestation), add a reconciliation validator, extend
`scripts/check_attestation.py` / diagnostics wiring, and supersede/annotate
ADR-0031 with a new ADR that records the harness-forced regime and the honest
remaining floor. Do NOT re-architect the attestation format from scratch.

**Key files + paths.**
- `docs/research/ORGANISM-PROGRAM-PLAN.md` — spec-of-record.
- `docs/adr/0031-wave-runner-attestation.md` — prior ATTEST-phase design.
- `scripts/wave_runner.py` — `run_wave`; add hash-chained ledger co-production.
- `scripts/check_attestation.py` — extend to reconcile ledger ↔ attestations.
- New reconciliation validator + CI/diagnostics wiring (paths per children).
- Committed wave-ledger + committed baseline grandfathering pre-regime tickets.
- Children: DAS-1504..1507.

## Acceptance criteria

- [ ] `run_wave` co-produces a COMMITTED, hash-chained wave-ledger entry
      atomically with the wave attestation (both land or neither does).
- [ ] A reconciliation validator enforces a bijection between ledger entries and
      attestations AND hash-chain continuity, and runs in CI + diagnostics.
- [ ] A wave-ledger gap (a skipped mid-sequence wave), a tampered entry, or an
      unattested recorded wave BREAKS the committed hash-chain → CI fails with
      teeth (demonstrated by a red-then-green test).
- [ ] A committed baseline grandfathers all pre-regime done tickets; the existing
      repo stays GREEN after the regime lands (diagnostics + CI pass).
- [ ] The new ADR records the harness-forced regime AND states the exact
      remaining floor HONESTLY: a wave that does zero committed work still leaves
      nothing to chain — but it also delivered nothing.
- [ ] Children DAS-1504..1507 are the decomposed implementation tickets under
      this epic.
- [ ] org-engine ticket — NO `project:` field; board_lint + check_never_auto_approve green.

## Log

### 2026-07-04 — CEO
Created from ORGANISM HARNESS-phase decomposition (/daslab-plan, audit-closure
final phase). Spec-of-record: docs/research/ORGANISM-PROGRAM-PLAN.md + the ATTEST
re-audit residual. READ: docs/adr/0031-wave-runner-attestation.md,
scripts/wave_runner.py, scripts/check_attestation.py,
docs/research/ORGANISM-PROGRAM-PLAN.md.

EPIC (audit-closure, final phase). The ATTEST phase (WS8) made partial/tampered
wave emission CI-detectable, but the re-audit found the IRREDUCIBLE residual: a
TOTAL silent omission (the orchestrator LLM never calls run_wave) leaves no
committed trace, so check_attestation (inert on an empty store) passes green.
This phase closes as much of that as an LLM-driven runtime allows by making the
attestation regime HARNESS-FORCED: run_wave co-produces a COMMITTED, hash-chained
wave-ledger (atomic with the attestation), and a reconciliation validator
enforces a bijection + chain-continuity in CI + diagnostics so that ANY recorded
wave that is skipped mid-sequence, tampered, or left unattested BREAKS a durable
committed hash-chain -> CI fails. A committed baseline grandfathers the
pre-regime done tickets. Children DAS-1504..1507. Acceptance: a wave-ledger
gap/tamper is CI-detected with teeth; the existing repo stays green (baseline);
the ADR records the exact remaining floor HONESTLY (a wave that does zero
committed work still leaves nothing — but it also delivered nothing).

Constraints: org-engine, NO project: field.

### 2026-07-04 — Orchestrator (/daslab-run)
Done. EPIC CLOSED — HARNESS phase complete. ADR-0032; run_wave co-produces a committed hash-chained board/wave-ledger.jsonl (atomic with the attestation, RAISES on failure); check_wave_reconciliation gate (bijection+chain+terminal+baseline) in CI+diagnostics; kill_drill proves the ledger chain survives a real SIGKILL (T5>=0.99, ledger_reconciles); /daslab-cycle collect documents the committed ledger + collect-time reconciliation. Moves the total-omission residual from silent-leaves-no-trace to omission-breaks-a-committed-chain (toward, not to, zero — a wave that commits ANY work can no longer hide). Children DAS-1504..1507 done.
