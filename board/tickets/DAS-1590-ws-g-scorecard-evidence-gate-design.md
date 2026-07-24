---
id: DAS-1590
title: WS-G Design — golden-eval scorecard and the 0 to 100 evidence gate design
status: todo
assignee: backend-em
author: ceo
dept: engineering
priority: p1
parent: DAS-1588
goal: mustaqil-ws-g-proof
spec: 007-mustaqil-ws-g-proof
implements: [FR-003, FR-004]
labels: [governance]
zone: docs/design
depends_on: [DAS-1589]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 2 — Design (closes GATE-2 for WS-G).** Design the scoring + evidence
machinery the Development tickets implement. No code beyond schemas/specs.

- **Run-scorecard (FR-003):** the machine-readable schema that scores the proof against
  each ED-1 completion-contract dimension (gates closed, merged PR + green CI, committed
  attestation, `diagnostics.py` 100/100, golden eval + anti-gaming probe). Design it as
  an **extension** of the existing eval substrate (`scripts/agent_eval.py`, `evals/`,
  `evals/e2e/`) — not a parallel harness. Specify the **anti-gaming probe** so a
  delivery cannot score green without real artifacts, and the SKIPPED-not-green rule
  for any dimension that cannot be measured (ADR-0020).
- **Evidence + attestation gate (FR-004):** how the 0→100 evidence trail is committed
  and hash-chained onto the existing wave attestation (ADR-0031/0032 — run-start /
  run-end / span / checkpoint / attestation), and how the gate rejects a false-green
  (a "done" with a missing or unmeasured artifact).
- Trace every design element to its FR and to ADR-0037 ED-1…ED-5.

Security Lead consulted (attestation integrity); accountable stage owner = CTO;
responsible = backend-em.

## Acceptance criteria
- [ ] Design doc under `docs/design/` covering the run-scorecard schema (per-dimension scoring + anti-gaming probe + SKIPPED-not-green), and the evidence/attestation gate contract (hash-chain onto ADR-0031/0032, false-green rejection) — each traced to its FR.
- [ ] The design extends `scripts/agent_eval.py` / `evals/` (extend-vs-new, ADR-0029), not a new parallel harness.
- [ ] Negative-path behaviour specified for SC-004 (a "done" with a missing/unmeasured artifact is rejected) so DAS-1594 can test it.
- [ ] Security Lead review recorded. `board_lint`/`check_spec_consistency` green. Merged PR, green CI.

## Log
### 2026-07-24 — Senior Product Manager
Created by /daslab-plan (WS-G Design). Scorecard (FR-003) + evidence/attestation gate
(FR-004) design; extends the existing eval substrate; anti-gaming + no-false-green.
</content>
