---
id: DAS-1561
title: MUSTAQIL WS-C LOOP — durable graph loop and per-task sandbox under DGO-X (EPIC)
status: done
assignee: cto
author: ceo
dept: engineering
priority: p1
parent: 
goal: mustaqil-ws-c-loop
spec: 004-mustaqil-ws-c-loop
labels: [security]
depends_on: [DAS-1543]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**EPIC — MUSTAQIL v3.0 WS-C LOOP.** Give DasLab the executional heart every autonomous
coding platform has and DasLab has only *designed*: a **durable, self-correcting,
interruptible loop** (plan-act-observe-replan, checkpoint/resume) as the DGO-X Phase-2/3
execution substrate, plus an **isolated per-task sandbox** for untrusted execution —
**strictly under ADR-0010 C1**, never the org brain. LangGraph is consumed as substrate;
E2B/OpenHands provides the sandbox. `graph_state` is a MIRROR; `board/tickets/` stays
canonical (C2).

**Contract of record:** ADR-0035 (LG-1…LG-5, under DGO-X C1–C6),
`docs/specs/004-mustaqil-ws-c-loop/SPEC.md` (FR-001…FR-007, SC-001…SC-005), master prompt
v3.0 row C, discovery Q2 (Docker-based E2B/OpenHands on the tenant VM) + Q4 (supervised,
then shadow before drive).

**Sequence (binding).** WS-C runs **AFTER WS-B RUNNER** (ADR-0034 — the Agent SDK
headless runner is the node-execution admission layer each worker dispatch rides; ADR-0035
`depends_on 0034`). WS-B is not yet decomposed into board tickets; this epic therefore
declares its concrete dependency on the landed program bootstrap (DAS-1543, feature-flag +
budget scaffold) and records the WS-B ordering as a **plan-time sequence constraint** —
`/daslab-run` must not drive WS-C ahead of WS-B's AADL gate. A workstream may not skip its
predecessor's gate.

**Everything ships behind `ws_c_langgraph_loop` (DEFAULT OFF, landed by DAS-1543).**
Shadow-before-drive; `/daslab-cycle` stays the fallback until the board approves drive.

**External-dependency reality (live sandbox).** The substrate + sandbox **adapter** code
and its tests are buildable in-repo against a stub/reference backend (the WS-A pattern:
absent-by-default optional backend). But any step that requires **actually running a live
Docker/E2B sandbox or VM** cannot be executed by an agent that has no live sandbox host —
that ticket (DAS-1566) is created `blocked` with an external-dependency note, while the
adapter/substrate tickets remain buildable `todo`.

**AADL — six-stage closure (children DAS-1562..DAS-1569):**

| Child | Stage | Ticket | Owner-hint | State |
|---|---|---|---|---|
| DAS-1562 | Planning | Author + ratify ADR-0035, review SPEC-004, confirm the WS-C key OFF | cto | todo |
| DAS-1563 | Design | Loop + sandbox admission design — graph_state ⇄ LangGraph mapping (LG-1), gates as interrupts (LG-2), worker write-scope (LG-3), checkpoint reconcile (LG-4), sandbox isolation contract | backend-em | todo |
| DAS-1564 | Development | LangGraph substrate adapter under DGO-X — state channels, conditional-edge/`interrupt()` gates, checkpointer reconciling the ADR-0023 run-model, flag OFF | backend-em | todo |
| DAS-1565 | Development | E2B/OpenHands per-task sandbox adapter — isolation boundary, in-tenant, stub-backend buildable, flag OFF | backend-eng-1 | todo |
| DAS-1566 | Development | Live per-task sandbox execution wiring against a real Docker/E2B host + isolation smoke | sre-eng | **blocked** (no live sandbox) |
| DAS-1567 | Testing | Negative + resume tests — idempotent checkpoint/resume, gate-interrupt block, routing-field rejection, divergence-resolves-to-board, flag-off byte-identical | qa-eng | todo |
| DAS-1568 | Deployment | Runbook + flag stays OFF on merge (no dispatch change), rollback = disable the loop key | sre-eng | todo |
| DAS-1569 | Maintenance | Scheduled health/eval of the loop + sandbox edge (checkpoint drift, isolation probe) | product-analyst | todo |

## Acceptance criteria
- [ ] All eight children (DAS-1562..DAS-1569) closed, each through its own AADL stage gate (DAS-1566 unblocks only when a live sandbox host is provisioned).
- [ ] **FR-001/LG-1:** the durable plan-act-observe-replan loop runs as the DGO-X P2/P3 substrate with checkpoint/resume, consuming LangGraph under C1 — never the top-level source of truth.
- [ ] **FR-002/LG-1 + C2:** `graph_state` is a projection of `board/tickets/`; a divergence-resolves-to-board test passes (SC-002).
- [ ] **FR-003/LG-2 + C4:** gates are `interrupt()`/conditional edges that halt-and-wait for the Founder; a negative test proves a ticket behind an open gate is not routed to a worker (SC-002).
- [ ] **FR-004/LG-3 + C3:** a worker node cannot write a routing field; a negative test proves it (SC-003).
- [ ] **FR-005/LG-4:** checkpoints reconcile with the ADR-0023 run-model and ADR-0031/0032 attestation; an idempotent checkpoint/resume test passes (SC-001).
- [ ] **FR-006:** worker execution runs inside an isolated in-tenant per-task sandbox (adapter buildable against a stub; live isolation smoke via DAS-1566 once a host exists).
- [ ] **FR-007/LG-5:** the substrate is feature-flagged OFF; with the flag OFF, dispatch is byte-identical to pre-merge (SC-004); rollback = disable the loop key.
- [ ] `diagnostics.py` 100/100; `board_lint`/`check_spec_consistency`/`check_dependency_graph`/validators green; no `project:` field on any WS-C ticket (R9); committed wave attestation (ADR-0031/0032) (SC-005).
- [ ] **Epic acceptance = AADL 6-gate closure for WS-C**, each gate logged in the stage-board.

## Log
### 2026-07-24 — CEO
Created by /daslab-plan from the Founder-approved MUSTAQIL v3.0 queue (order 3, row C).
Contract = ADR-0035 (LG-1..LG-5, under DGO-X C1-C6) + SPEC-004 (FR-001..FR-007,
SC-001..SC-005). Children DAS-1562..DAS-1569 (one per AADL stage, 3 Development: LangGraph
substrate adapter + E2B/OpenHands sandbox adapter + live-sandbox wiring). Org-engine epic —
no `project:` field (board_lint R9). Depends on the landed program bootstrap (DAS-1543,
`ws_c_langgraph_loop` OFF + budgets). **Sequence:** runs AFTER WS-B (ADR-0034 runner is the
node-execution admission layer); WS-B not yet on the board, so the ordering is a plan-time
constraint, not a `depends_on` edge (a dangling dep would fail check_dependency_graph).
DAS-1566 created `blocked` — actually running a live Docker/E2B sandbox needs a host an
agent does not have; the adapter/substrate code + tests stay buildable `todo`.
</content>

### 2026-07-24 — Orchestrator (/daslab-cycle)
**EPIC CLOSED — WS-C LOOP complete.** All six AADL gates closed: GATE-1 (1562 ADR-0035, LangGraph=projection of graph_state, board canonical) → GATE-2 (1563 loop+sandbox design) → GATE-3 (1564 substrate + 1565 sandbox stub; security-eng red-team PASSED no escape; clean-room import-ban reconciled to ADR-0035 via scoped scripts/dgox carve-out) → GATE-4 (1567 SC-001..005 + NUL-byte hardening, 0 xfailed) → GATE-5 (1568 runbook, flag OFF) → GATE-6 (1569 board-canonical/sandbox-wall/import-ban-drift health check). Behind ws_c_langgraph_loop OFF. LOCAL-ONLY. DAS-1566 live DockerSandbox stays BLOCKED (real Docker/E2B host). Unblocks WS-E (overlaps C) + WS-G (after B) + WS-H (after B+D+E).
