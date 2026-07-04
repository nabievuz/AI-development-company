---
id: DAS-1497
title: ORGANISM — ATTEST (deterministic wave-runner)
status: done
assignee: cto
author: ceo
dept: engineering
priority: p1
parent: 
goal: organism-ws8-attest
created: 2026-07-03
updated: 2026-07-03
---

## Description

**EPIC — audit-closure phase.** This epic closes the ORGANISM self-audit's
central seam: **"documented >> enforced."** Today the entire wave lifecycle —
emitting `run_start` / `run_end` / `span` events, checkpointing, applying
guardrails, appending to the ledger, and committing evidence — lives as PROSE
inside `.claude/skills/daslab-cycle/SKILL.md` and is executed by the
orchestrator LLM by reading and following that prose. Because nothing
deterministic runs, the event-based gates (T1–T7, spans, cost, evidence) are
**perma-inert in CI**: `check_spans`, `check_metric_gaming`, and `check_ledger`
have no real event stream to compute over, so enforcement rides entirely on LLM
compliance. If the LLM skips or garbles a step, no gate notices.

**What this phase does:** move the wave-lifecycle MECHANICS out of SKILL prose
and into a DETERMINISTIC Python **wave-runner** that the LLM calls exactly ONCE
per wave. The division of labor is deliberate: **the LLM still makes the routing
DECISION** (which tickets, which owners, which models) — the runner only
EXECUTES the post-decision mechanics (emit events, checkpoint, guardrails,
ledger, evidence commit). This makes the lifecycle END-TO-END TESTABLE and
produces a COMMITTED **attestation** artifact that a validator can gate on in
CI, replacing "trust the LLM followed the prose" with "the runner ran and left
proof."

**Extend vs. new:** EXTEND the existing dispatch/evidence plumbing rather than
forking it. `scripts/dispatch_emitter.py` and `scripts/snapshot_evidence.py`
already model dispatch/evidence emission — the wave-runner should wrap and drive
these, not duplicate them. The event gates (`check_spans`,
`check_metric_gaming`, `check_ledger`) already exist as validators — this phase
FEEDS them real data and adds a committed attestation + a validator that gates
on it. Do not rewrite the SKILL's routing/decision logic; only relocate the
mechanical steps it currently narrates.

**Key files + paths:**
- `docs/research/ORGANISM-PROGRAM-PLAN.md` — spec-of-record (+ the closing
  self-audit that names this seam).
- `.claude/skills/daslab-cycle/SKILL.md` — current PROSE home of the wave
  lifecycle; the mechanics move OUT of here.
- `scripts/dispatch_emitter.py` — existing dispatch-event emission to
  wrap/drive.
- `scripts/snapshot_evidence.py` — existing evidence snapshot/commit to
  wrap/drive.
- New: a deterministic `wave_runner` (Python) the LLM calls once; a committed
  attestation artifact; a validator that gates CI on it.

**Children:** DAS-1498 .. DAS-1502 (decomposed under this epic).

**Constraints:** org-engine / DasLab-platform work only. This ticket carries NO
`project:` field (board_lint R9). Enforcement mechanics must have TEETH — a gate
that cannot fail on bad input is not done.

## Acceptance criteria

- [ ] A deterministic Python **wave-runner** exists that the orchestrator LLM
      invokes ONCE per wave; the LLM retains the routing DECISION, the runner
      executes all post-decision mechanics (emit `run_start`/`run_end`/`span`,
      checkpoint, guardrails, ledger append, evidence commit).
- [ ] The wave-runner wraps/drives the existing `scripts/dispatch_emitter.py`
      and `scripts/snapshot_evidence.py` (extends, does not duplicate).
- [ ] A synthetic wave pushed through the REAL `wave_runner` makes
      `check_spans`, `check_metric_gaming`, and `check_ledger` compute REAL
      numbers with TEETH (they can and do FAIL on bad/gamed input) — covered by
      tests.
- [ ] A COMMITTED **attestation** artifact is produced per wave and a validator
      GATES on it in CI (missing/invalid attestation fails the gate).
- [ ] The wave lifecycle mechanics are removed from SKILL prose (or the prose
      now points at the runner) — the mechanics no longer depend on LLM
      narration.
- [ ] **flag-on == flag-off** for DISPATCH DECISIONS: routing outcomes are
      preserved whether the deterministic runner path is enabled or not
      (behavior-preserving relocation, verified).
- [ ] Children DAS-1498 .. DAS-1502 reference this epic as `parent`.
- [ ] org-engine only; no `project:` field; `scripts/board_lint.py` passes.

## Log

### 2026-07-03 — CEO
Created from ORGANISM ATTEST-phase decomposition (/daslab-plan, audit-closure).
Spec-of-record: docs/research/ORGANISM-PROGRAM-PLAN.md + the closing self-audit.
READ: docs/research/ORGANISM-PROGRAM-PLAN.md, .claude/skills/daslab-cycle/SKILL.md,
scripts/dispatch_emitter.py, scripts/snapshot_evidence.py.
This epic moves the wave-lifecycle mechanics out of SKILL prose into a
deterministic Python wave-runner (LLM decides routing, runner executes
mechanics), makes them end-to-end testable, and commits an attestation a
validator gates on. Children DAS-1498..1502. Closes the "documented >> enforced"
seam so T1–T7 / spans / cost / evidence gates stop being perma-inert.

### 2026-07-03 — Orchestrator (/daslab-run)
EPIC CLOSED — ATTEST phase complete. ADR-0031 (deterministic wave-runner + attestation); scripts/wave_runner.py (run_wave: 6 mechanics, LLM supplies plan+results as DATA, no decision inside) + end-to-end teeth test; scripts/check_attestation.py gate + committed sample (bites in CI) wired into diagnostics+ci; kill_drill retrofit through the REAL wave_runner (crash+resume on the production lifecycle); /daslab-cycle collapsed to a single run_wave call (done-ness flows through the attested runner). Closes the self-audit's core 'documented>>enforced' seam for the wave lifecycle: event invariants now enforced through a tested code path + committed attestations, LLM-compliance surface shrunk to ONE call whose omission is DETECTABLE (no attestation -> CI fails). Latent guardrails_dir default bug (DAS-1501 finding) fixed + regression-tested. Children DAS-1498..1502 done.
