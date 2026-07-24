---
id: DAS-1564
title: WS-C Development — LangGraph substrate adapter under DGO-X, state channels, interrupt gates, checkpointer
status: todo
assignee: backend-em
author: ceo
dept: engineering
priority: p1
parent: DAS-1561
goal: mustaqil-ws-c-loop
spec: 004-mustaqil-ws-c-loop
implements: [FR-001, FR-002, FR-003, FR-005]
labels: [governance]
zone: scripts/dgox
depends_on: [DAS-1563]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 3 — Development (closes GATE-3 for WS-C, part 1).** Build the LangGraph
execution substrate for DGO-X Phases 2–3 per the DAS-1563 design, **strictly under C1**
(substrate, not the org brain).

- **LG-1/FR-001:** the durable plan-act-observe-replan loop as LangGraph state channels +
  conditional edges + a checkpointer; each worker node is a Claude Agent SDK dispatch
  (ADR-0034 — the WS-B runner is the node-execution admission layer, not re-opened here).
- **LG-1/FR-002/C2:** map `scripts/dgox/state.py:graph_state` to LangGraph channels with
  identical per-field write authority; the LangGraph state is a **projection** of
  `board/tickets/`; a divergence reconciles to the board (board wins).
- **LG-2/FR-003/C4:** AADL gates are conditional edges; security/budget/never-auto-approve
  are `interrupt()` points that halt-and-wait for the Founder; a ticket behind an open gate
  is not routed to a worker node.
- **LG-4/FR-005:** the checkpointer **reconciles with** (never forks) the ADR-0023
  run-model and the ADR-0031/0032 attestation + wave-ledger; the graph runs post-decision
  mechanics through `run_wave` so ADR-0025 flag-on==flag-off holds.
- **LG-5/FR-007:** everything behind `ws_c_langgraph_loop` (OFF); with the flag OFF the
  substrate is inert and dispatch is byte-identical to pre-merge; `/daslab-cycle` stays the
  fallback.

Hand the matching negative/resume tests to DAS-1567. Distinct repo zone (`scripts/dgox/`)
from the sandbox adapter (DAS-1565) so the two Development tickets don't collide in one wave.

## Acceptance criteria
- [ ] LangGraph substrate under `scripts/dgox/` runs the durable loop with checkpoint/resume; LangGraph is consumed as substrate, never treated as the source of truth (a PR that treats graph state as truth is rejected — LG-1/C2).
- [ ] `graph_state` ⇄ LangGraph channel mapping present with matching write authority; a divergence reconciles to the board.
- [ ] Gates implemented as conditional edges / `interrupt()`; a ticket behind an open gate is not routed to a worker (LG-2/C4).
- [ ] Checkpointer reconciles with the ADR-0023 run-model + ADR-0031/0032 attestation (no forked truth); flag-on==flag-off dispatch (LG-4/ADR-0025).
- [ ] Feature flag OFF by default; flag-off behaviour byte-identical to pre-merge; `diagnostics.py` 100/100. Merged PR, green CI.

## Log
### 2026-07-24 — CEO
Created by /daslab-plan (WS-C Development, part 1). LG-1 loop + LG-2 gate-interrupts + LG-4
checkpoint reconcile, all under C1 and behind `ws_c_langgraph_loop` OFF. Node execution
rides the ADR-0034 WS-B runner (admission layer not re-opened here).
</content>
