---
id: DAS-1588
title: MUSTAQIL WS-G PROOF — one project delivered 0 to 100 autonomously (EPIC)
status: backlog
assignee: cto
author: ceo
dept: engineering
priority: p1
parent: 
goal: mustaqil-ws-g-proof
spec: 007-mustaqil-ws-g-proof
labels: [governance]
depends_on: [DAS-1543]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**EPIC — MUSTAQIL v3.0 WS-G PROOF.** Prove the finisher is real: take ONE scoped
project from **0 to 100 autonomously** through all six AADL gates on self-host infra,
with a committed evidence trail and attestation. This is the MUSTAQIL completion
contract made concrete — not asserted omnicompetence, but **one delivered project**
(ED-5). Founder Q1 fixed the proof scope = the **WS-H dashboard slice** (e.g. the
CP-3b trigger-run): building it dogfoods and proves the finisher at once.

**Contract of record:** ADR-0037 (ED-1…ED-5 — the completion contract),
`docs/specs/007-mustaqil-ws-g-proof/SPEC.md` (FR-001…FR-008, SC-001…SC-005), master
prompt v3.0 Part 1 row G + Part 2 (DONE=100), discovery Q1 (proof = WS-H slice) + Q7
(shipped = merged + green CI + deployed to the tenant VM).

**Sequence:** **after WS-B** — the proof runs on the ADR-0034 headless runner, so
WS-G may not skip WS-B's AADL gate (master prompt Part 1 Sequence). Concrete scaffold
dependency = the program bootstrap DAS-1543 (budgets, `ws_g_proof` flag OFF, TN-1).

**Two placement layers (QONUN — Project Placement Law):**
- The **org-engine WS-G machinery** lives here in `board/tickets/` (NO `project:`
  field): the completion contract (ADR-0037), the golden-eval / SWE-bench harness +
  run-scorecard, the 0→100 evidence + attestation gate, and the decision that fixes
  the proof scope.
- The **actual proof PROJECT** built 0→100 lives under `projects/<proof-name>/` and
  runs its OWN six AADL gates on its OWN board (`projects/<proof-name>/board-tickets/`).
  Its project tickets are created LATER, when WS-G executes — NOT now. DAS-1593 only
  bootstraps the `projects/<proof-name>/` skeleton (AI-agent-lifecycle §2) so the proof
  can then run its own lifecycle; no project ticket is authored on the org board.

**AADL — six-stage closure (children DAS-1589..DAS-1596):**

| Child | Stage | Ticket | Owner-hint |
|---|---|---|---|
| DAS-1589 | Planning | Author + ratify ADR-0037, review SPEC-007, fix the proof scope (Q1 WS-H slice) | cto |
| DAS-1590 | Design | Golden-eval scorecard + the 0→100 evidence-gate / attestation design | backend-em |
| DAS-1591 | Development | Golden-eval / SWE-bench harness + run-scorecard (extends `scripts/agent_eval.py`, `evals/`) | backend-em |
| DAS-1592 | Development | The 0→100 evidence + attestation gate, no false-green (ADR-0020/0031/0032) | backend-eng-1 |
| DAS-1593 | Development | Bootstrap the proof-project skeleton under `projects/<proof-name>/` (AADL §2) | backend-em |
| DAS-1594 | Testing | Negative tests — false-green rejected, dimension-skip not-green, flag-OFF no-op | qa-eng |
| DAS-1595 | Deployment | Deploy the proof to the tenant VM (Q7) — **BLOCKED, external, no VM this session** | sre-eng |
| DAS-1596 | Maintenance | Scheduled scorecard / evidence health + drift on the eval cadence | product-analyst |

## Acceptance criteria
- [ ] All eight children (DAS-1589..DAS-1596) closed, each through its own AADL stage gate.
- [ ] **FR-001:** the proof scope is Founder-fixed (Q1 WS-H slice) and treated as immutable — no self-scoping; an ambiguous boundary halts at Clarify (ADR-0014) + escalates.
- [ ] **FR-002/ED-1:** "finished" is evidenced ONLY (gates closed, merged PR + green CI, committed attestation, diagnostics 100/100, golden eval + anti-gaming probe); unmeasured is SKIPPED, never green (SC-001).
- [ ] **FR-003:** a golden-eval / SWE-bench-style run-scorecard scores the proof against the contract and extends the existing eval substrate (not a parallel harness).
- [ ] **FR-004/ADR-0020/0031/0032:** the 0→100 evidence trail is committed + hash-chained and the gate rejects a false-green (SC-004).
- [ ] **FR-005:** the proof project lives entirely under `projects/<proof-name>/`, bootstrapped from the AADL §2 skeleton, running its OWN six gates; no `project:` field on any WS-G org-engine ticket (R9).
- [ ] **FR-006/Q7:** "shipped" = merged + green CI + deployed to the tenant VM; absent a VM the deploy step is `blocked` with a precise reason, never faked (SC-002).
- [ ] **FR-007:** the WS-G machinery is behind `ws_g_proof` OFF; with the flag OFF dispatch is byte-identical to pre-merge (SC-003).
- [ ] **FR-008/ED-2:** the only legitimate halt is a Founder/AADL gate; a blocked unit opens a `blocked` ticket + escalates, never runs past.
- [ ] `diagnostics.py` 100/100; `board_lint`/`check_spec_consistency`/`check_dependency_graph`/validators green; committed wave attestation (SC-005).
- [ ] **Epic acceptance = AADL 6-gate closure for WS-G**, each gate logged in the stage-board.

## Log
### 2026-07-24 — Senior Product Manager
Created by /daslab-plan from the Founder-approved MUSTAQIL v3.0 queue (WS-G PROOF).
Contract = ADR-0037 (ED-1..ED-5) + SPEC-007. Children DAS-1589..DAS-1596 (one per
AADL stage, 3 Development: harness, evidence-gate, proof-project bootstrap).
Org-engine epic — no `project:` field (board_lint R9). Sequence: after WS-B; concrete
scaffold dep = DAS-1543. The proof PROJECT (Founder Q1 = WS-H dashboard slice) is
bootstrapped under `projects/<proof-name>/` by DAS-1593 and runs its OWN six gates —
no project ticket on the org board. Deployment (DAS-1595) is BLOCKED pending a
provisioned tenant VM (external, Q7). Escalation to CPO noted in report: the proof
scope fix (Q1) is confirmed by the Founder discovery record but its ADR ratification
is a CTO act (DAS-1589), above PM authority.
</content>
