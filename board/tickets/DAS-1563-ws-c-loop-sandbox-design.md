---
id: DAS-1563
title: WS-C Design — durable loop and sandbox admission model, state mapping, gates as interrupts
status: todo
assignee: backend-em
author: ceo
dept: engineering
priority: p1
parent: DAS-1561
goal: mustaqil-ws-c-loop
spec: 004-mustaqil-ws-c-loop
implements: [FR-002, FR-003, FR-004, FR-006]
labels: [governance, security]
zone: docs/design
depends_on: [DAS-1562]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 2 — Design (closes GATE-2 for WS-C).** Design the governed execution model
the Development tickets implement. No code beyond schemas/specs. Security Lead consulted on
the sandbox isolation contract (accountable stage owner = CTO; responsible = backend-em).

- **State mapping (LG-1 / FR-002 / C2):** how `scripts/dgox/state.py:graph_state` maps to
  LangGraph state channels *with the same per-field write authority*; how the LangGraph
  state stays a **projection** of `board/tickets/` and how a divergence resolves to the
  board (board wins). Name where reconciliation happens.
- **Gates as edges/interrupts (LG-2 / FR-003 / C4):** how each AADL predecessor gate
  becomes a conditional edge, and how security / budget / never-auto-approve categories
  become `interrupt()` points that halt-and-wait for the Founder — a ticket behind an open
  gate is not routed to a worker node.
- **Worker write-scope (LG-3 / FR-004 / C3):** the invariant that a worker node edits only
  its ticket body/log + artifacts, never a routing field (assignee/reviewer/routing_reason/
  confidence) — supervisor-only, matching the ADR-0011 Routing-group invariant.
- **Checkpoint reconcile (LG-4):** how LangGraph checkpoints reconcile with (never fork)
  the ADR-0023 run-model and the ADR-0031/0032 attestation + wave-ledger; how flag-on ==
  flag-off dispatch holds (ADR-0025).
- **Sandbox isolation contract (FR-006):** the per-task sandbox boundary (E2B/OpenHands,
  Docker-based per Q2) — what a worker node may reach inside it, and the fail-closed rule
  that untrusted execution cannot reach the host, the repo, another task, or an unscoped
  credential. Name the stub/reference backend so the adapter is buildable without a live
  host, and mark the live-host isolation smoke as DAS-1566 (external dependency).

## Acceptance criteria
- [ ] Design doc under `docs/` covering the graph_state ⇄ LangGraph channel mapping (with write authority), the gate-as-interrupt contract, the worker write-scope invariant, the checkpoint-reconcile rule, and the sandbox isolation contract — each traced to its FR and LG invariant.
- [ ] Negative-path behaviour specified for SC-001/SC-002/SC-003 (idempotent resume, gate-block, divergence-resolves-to-board, routing-field rejection) so DAS-1567 can test it.
- [ ] Sandbox stub/reference backend named so DAS-1565 builds without a live host; live-host smoke scoped to DAS-1566.
- [ ] Security Lead review recorded. `board_lint`/`check_spec_consistency` green. Merged PR, green CI.

## Log
### 2026-07-24 — CEO
Created by /daslab-plan (WS-C Design). LG-1 state mapping, LG-2 gates-as-interrupts, LG-3
worker write-scope, LG-4 checkpoint reconcile, and the per-task sandbox isolation contract.
Security Lead consulted on the sandbox boundary.
</content>
