# SPEC 007 — MUSTAQIL WS-G PROOF (one project delivered 0→100 autonomously)

- **Goal:** mustaqil-ws-g-proof
- **Owner:** backend-em
- **Status:** reviewed (CTO — 2026-07-24, WS-G GATE-1; all functional requirements and success criteria judged coherent, testable, and traceable to ADR-0037 ED-1…ED-5; no open clarification markers)

> WHAT/WHY only. The HOW (harness module layout, scorecard schema fields, the
> attestation hash-chain wiring, the project-skeleton generator) lives in ADR-0037
> and the AADL Stage-2/Stage-3 tickets, not here. Binds to ADR-0037 (ED-1…ED-5 —
> the MUSTAQIL completion contract), the master prompt
> (`docs/research/2026-07-23-daslab-mustaqil-master-prompt-v3.md` Part 1 row G +
> Part 2 DONE=100), Founder discovery answers Q1 (proof = the WS-H dashboard slice)
> and Q7 (shipped = merged + green CI + deployed to the tenant VM), and enforces
> ADR-0020 (no false-green) and ADR-0031/0032 (wave attestation).

## User Scenarios

- **P1 —** Given the Founder-fixed proof scope, when WS-G runs, then exactly one
  scoped project is delivered end-to-end through its own six AADL gates on self-host
  infra, with no widening and no narrowing of that scope — an unclear boundary halts
  at the Clarify gate and escalates rather than being re-scoped silently.
- **P1 —** Given a completed unit of proof work, when it is claimed "done", then the
  claim is accepted only when it is backed by a real artifact — a merged PR, green CI,
  a committed hash-chained attestation, a passing golden eval — and a claim without an
  artifact is treated as false, never green.
- **P1 —** Given the WS-G feature flag is OFF (default), when a wave runs, then the
  scorecard/harness is inert and dispatch behaviour is byte-identical to pre-merge —
  the WS-G machinery simply does not exist for the org.
- **P2 —** Given the proof delivery, when the run-scorecard is produced, then it scores
  every dimension of the completion contract, and any dimension that cannot be measured
  is reported as skipped rather than counted as passing.
- **P2 —** Given a unit of proof work that cannot proceed, when it hits a real blocker,
  then it opens a blocked ticket with the exact reason and escalates — it never loops,
  guesses past the block, or reports a false success.
- **P2 —** Given the proof project is a distinct deliverable, when it is bootstrapped,
  then it lives entirely under `projects/<proof-name>/` per the Project Placement Law,
  and its own work tickets live on the project's own board — never in the org
  `board/tickets/`.

## Functional Requirements

- **FR-001** — The proof scope MUST be fixed by the Founder decision (Q1 — the WS-H
  dashboard slice, e.g. the CP-3b trigger-run) and treated as immutable by the run:
  no self-scoping (no widening, no narrowing to what is easy); an ambiguous boundary
  MUST pass the Clarify gate (ADR-0014) and escalate, never be re-scoped silently
  (ED-5).
- **FR-002** — "Finished" (0→100) MUST be defined ONLY by evidence: every AADL gate
  closed; every code ticket a merged PR with green CI; every wave a committed
  hash-chained attestation; `diagnostics.py` = 100/100 on a clean tree; and golden
  evals passing with the anti-gaming probe. No prose "done", no self-report, and no
  unmeasured dimension counts — unmeasured is SKIPPED, never green (ED-1, ADR-0020).
- **FR-003** — A golden-eval / SWE-bench-style harness MUST score the proof delivery
  against the completion contract and emit a machine-readable run-scorecard; it MUST
  extend the existing eval substrate (`scripts/agent_eval.py`, `evals/`) rather than
  stand up a parallel harness, and MUST include an anti-gaming probe so a delivery
  cannot be scored green without real artifacts.
- **FR-004** — The 0→100 evidence trail MUST be committed and hash-chained per
  ADR-0031/0032 (run-start / run-end / span / checkpoint / attestation), so a lapse
  breaks a committed chain and fails CI rather than passing silently; the evidence gate
  MUST reject a false-green (a "done" with a missing or unmeasured artifact) (ADR-0020).
- **FR-005** — The proof PROJECT MUST live entirely under `projects/<proof-name>/`,
  bootstrapped from the AI-agent-lifecycle §2 canonical skeleton, and MUST run its OWN
  six AADL gates; its work tickets MUST live on the project's own board
  (`projects/<proof-name>/board-tickets/`), never in the org `board/tickets/`, and no
  org-engine WS-G ticket MUST carry a `project:` field (QONUN — Project Placement Law).
- **FR-006** — "Shipped" for the proof MUST mean merged to `main` + green CI +
  **deployed to the tenant VM** (Q7); the deploy-to-VM step is an external dependency
  (a provisioned tenant VM) and, absent that infra, MUST be recorded as `blocked` with
  a precise reason rather than skipped, faked, or reported green.
- **FR-007** — The WS-G machinery (harness, scorecard, evidence gate) MUST be
  feature-flagged in `config/features.yaml` DEFAULT **OFF** (`ws_g_proof`); adding it
  MUST change no dispatch behaviour on merge, and with the flag OFF the harness/scorecard
  MUST be inert.
- **FR-008** — The only legitimate halt in the proof run MUST be a sanctioned
  Founder/AADL gate: the org advances to the gate, presents evidence, and waits for a
  Founder-identity approval (never a chat string or a non-Founder actor); a blocked unit
  MUST open a `blocked` ticket with the exact reason and escalate (ROUTING.md), never
  run past the gate or the block (ED-2).

## Success Criteria

- **SC-001** — The run-scorecard proves each completion-contract dimension for the proof
  (gates closed, PR + green CI, committed attestation, `diagnostics.py` 100/100, golden
  eval + anti-gaming probe); a dimension that cannot be measured is reported skipped,
  never counted green.
- **SC-002** — The proof project is delivered 0→100 through its own six AADL gates on
  self-host infra with a committed evidence trail; the deploy-to-VM step is either
  evidenced or, absent the VM, carried as `blocked` with a precise reason (never faked).
- **SC-003** — With `ws_g_proof` OFF, a wave's dispatch behaviour is byte-identical to
  pre-merge and the harness/scorecard is inert; flipping it ON exposes only the scoring
  machinery, changing no dispatch behaviour.
- **SC-004** — A false-green attempt — a unit claimed "done" with a missing or unmeasured
  artifact — is caught by the evidence gate / anti-gaming probe and fails, proven by a
  negative test.
- **SC-005** — `diagnostics.py` 100/100, `board_lint` / `check_spec_consistency` /
  `check_dependency_graph` green, green CI on every WS-G PR, no `project:` field on any
  WS-G org-engine ticket (board_lint R9), and a committed wave attestation.
</content>
</invoke>
