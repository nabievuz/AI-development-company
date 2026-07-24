---
id: DAS-1552
title: MUSTAQIL WS-B RUNNER — headless Claude Agent SDK dispatch (EPIC)
status: done
assignee: cto
author: ceo
dept: engineering
priority: p1
parent:
goal: mustaqil-ws-b-runner
spec: 003-mustaqil-ws-b-runner
labels: [security, governance]
depends_on: [DAS-1544]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**EPIC — MUSTAQIL v3.0 WS-B RUNNER.** Give DasLab a programmatic (headless)
dispatch entrypoint over the **Claude Agent SDK / `claude -p`** — a thin
`daslab_sdk` runner that loads the repo's own agents/skills/`CLAUDE.md`/hooks/
`.mcp.json` unmodified and dispatches a ticket (and, via a wave call, a whole
wave) against the same repo, additive to `/daslab-cycle`. Authentication is a
**Claude subscription account** (Pro/Max/Team/Enterprise), never a metered API
key; the monthly subscription credit is the SI-5 hard budget ceiling; credit
exhaustion is a **sanctioned pause**, not a failure.

**Contract of record:** ADR-0034 (SR-1…SR-5),
`docs/specs/003-mustaqil-ws-b-runner/SPEC.md` (FR-001…FR-008, SC-001…SC-005),
master prompt v3.0 Part 1 row B + Part 2, discovery answer Q9 (Claude
subscription, account auth, monthly credit = hard ceiling, credit exhaustion =
sanctioned pause).

**Sequence — runs AFTER WS-A.** Per the master prompt's workstream order
(`A → B → C`), WS-B may not open its Planning gate until WS-A's own AADL
closure has progressed far enough to trust the governed MCP tool edge the
runner will eventually dispatch through; this epic and its Planning child
`depends_on` the WS-A epic (`DAS-1544`) to encode that ordering. No stage of
WS-B may skip a predecessor's AADL gate (QONUN — AI Agent Lifecycle).

**Standing caveat carried forward (not a blocker, verify at build/flip time):**
the 2026-06-15 Agent-SDK credit model was announced then paused — the exact
live per-plan terms MUST be re-confirmed before the feature flag is ever
flipped ON (see the Planning child's `[NEEDS CLARIFICATION]` marker).

**AADL — six-stage closure (children DAS-1553..DAS-1559):**

| Child | Stage | Ticket | Owner-hint |
|---|---|---|---|
| DAS-1553 | Planning | Ratify ADR-0034 + review SPEC-003 + carry the Q9 build-time verification marker | cto |
| DAS-1554 | Design | `daslab_sdk` call-shape design — agent/skill/hook load (SR-1), explicit-model + admission-gateway contract (SR-2), the `run_wave` boundary + event/attestation reuse (SR-3), board/git-law boundary (SR-4), auth + budget/credit-ceiling integration | backend-em |
| DAS-1555 | Development | `daslab_sdk` core runner — load the repo's own charter, call `scripts/wave_runner.py:run_wave`, emit the standard event/attestation stream, flag OFF | backend-em |
| DAS-1556 | Development | Admission-gateway wiring — explicit per-dispatch model, Claude-subscription account auth (not an API key), monthly-credit ceiling + budget-breach idle+alert + sanctioned-pause handling | backend-eng-1 |
| DAS-1557 | Testing | Dispatch-equivalence, missing-model rejection, flag-off no-op, and budget/credit-exhaustion negative tests | qa-eng |
| DAS-1558 | Deployment | Runbook + flag stays OFF on merge (no dispatch change), rollback plan | sre-eng |
| DAS-1559 | Maintenance | Scheduled health/eval of the runner path (dispatch-equivalence drift, budget-ceiling drift) | product-analyst |

## Acceptance criteria
- [ ] All seven children (DAS-1553..DAS-1559) closed, each through its own AADL stage gate.
- [ ] **FR-001/SR-1:** every dispatch loads the repo's own agents/skills/`CLAUDE.md`/hooks/`.mcp.json` unmodified; porting the guild roles to a different agent abstraction is forbidden.
- [ ] **FR-002/SR-2:** every dispatch carries an explicit model sourced from `governance/policies/model-allocation.md`; the runner is the ADR-0009 admission gateway; a negative test proves a dispatch without an explicit model is rejected (SC-002).
- [ ] **FR-003/SR-3:** the runner makes no routing/selection/re-tier decision of its own — it calls the existing `run_wave` function and emits the standard event/attestation stream; a dispatch-equivalence test proves a headless wave and an interactive wave produce the same board/event outcome (SC-001).
- [ ] **FR-004/SR-4:** the board stays canonical; a code-touching ticket dispatched headlessly still gets its own worktree/branch/PR; the runner never merges its own PR.
- [ ] **FR-005/SR-5:** the runner is feature-flagged OFF by default (`ws_b_agent_sdk_runner`); with the flag OFF, `/daslab-cycle` dispatch is byte-identical to pre-merge (SC-003).
- [ ] **FR-006:** the runner authenticates via a Claude-subscription account (Pro/Max/Team/Enterprise), never a metered API key, routed through the admission layer.
- [ ] **FR-007/FR-008:** a budget-breach or monthly-credit-exhaustion scenario is proven, by test, to evaluate to idle+alert / a sanctioned pause — never a false-green or an unhandled crash (SC-004).
- [ ] `diagnostics.py` 100/100; `board_lint`/`check_spec_consistency`/`check_dependency_graph` all green; no `project:` field on any WS-B ticket (R9); committed wave attestation (ADR-0031/0032).
- [ ] **Epic acceptance = AADL 6-gate closure for WS-B**, each gate logged in the stage-board.

## Log
### 2026-07-24 — Senior PM
Created by `/daslab-plan` from the Founder-approved MUSTAQIL v3.0 queue, WS-B RUNNER
(order 2, after WS-A). Contract = ADR-0034 (SR-1..SR-5) + SPEC-003
(`docs/specs/003-mustaqil-ws-b-runner/SPEC.md`). Children DAS-1553..DAS-1559 (one per
AADL stage, 2 Development tickets split by zone — `daslab_sdk` core runner vs the
admission-gateway/auth/budget wiring — so they can dispatch in the same wave without a
zone collision). Org-engine epic — no `project:` field (board_lint R9). `depends_on:
[DAS-1544]` encodes the master-prompt sequencing rule "A → B": WS-B may not open its
Planning gate ahead of WS-A. No code/ADR/config touched by this planning pass; only
this ticket file, its seven children, and the SPEC-003 directory were created.

### 2026-07-24 — Orchestrator (/daslab-cycle)
**EPIC CLOSED — WS-B RUNNER complete.** All six AADL gates closed: GATE-1 Planning (DAS-1553, ADR-0034 ratified + 2 clarification markers resolved as a DAS-1558 flip-time precondition) → GATE-2 Design (DAS-1554, run_wave boundary + subscription-auth design) → GATE-3 Development (DAS-1555 daslab_sdk core + DAS-1556 admission gateway; CTO Option-B on the 5→2 admission adapter seam, ANTHROPIC_API_KEY-drop verified) → GATE-4 Testing (DAS-1557, integration adapter proves the enum-trap fix + negative suite) → GATE-5 Deployment (DAS-1558, flip runbook; live-terms precondition honestly UNRESOLVED = flip held OFF by design) → GATE-6 Maintenance (DAS-1559, dispatch-equivalence + budget-drift health check). Behind `ws_b_agent_sdk_runner` OFF — no live headless drive. LOCAL-ONLY (nothing pushed). Unblocks WS-C (DAS-1561, after B) — WS-D (DAS-1570) was already unblocked (parallel from A).
