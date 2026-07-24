# ADR 0035 — LangGraph as the DGO-X P2/P3 execution substrate (under C1, never the org brain)

- **Status:** Accepted (Backend EM authors; **CTO ratified — RACI 3.1/3.6 A — 2026-07-24**; Security Lead consulted — sandbox, secrets)
- **Date:** 2026-07-22 (ratified 2026-07-24)
- **Scope:** Platform / orchestration — the executing engine for DGO-X Phases 2–3
- **Deciders:** Backend EM (author), **CTO (accountable)**; Security Lead (consulted — sandboxed worker runner)
- **Relates:** **extends** [0010](0010-adopt-dgox-graph-orchestrated-control-plane.md) (DGO-X target + C1–C6); depends on [0034](0034-agent-sdk-headless-runner.md) (node execution); reconciles with [0023](0023-run-model.md) (checkpoints), [0025](0025-events-load-bearing.md) (flag-on==flag-off), [0031](0031-wave-runner-attestation.md)/[0032](0032-harness-forced-attestation.md) (attestation); direction brief `docs/research/2026-07-22-daslab-devin-langchain-direction.md`
- **Supersedes / Amends:** nothing — implements DGO-X P2/P3 with an adopted substrate; C1–C6 apply verbatim.

> DGO-X (ADR 0010) already specifies a deterministic supervisor + gate engine (P2), a sandboxed worker runner (P3), and checkpoint/resume it calls *"LangGraph-style persistence."* Rather than hand-build that engine, this ADR adopts **LangGraph** as the substrate — the durable, self-correcting, interruptible loop that makes DasLab *operate* like the autonomous coding platforms — **strictly under DGO-X**, never as the top-level source of truth.

## Context

The parity analysis names the durable agentic loop (plan→act→observe→replan, resumable, with human interrupts) as the executional heart every competitor has and DasLab has only *designed*. ADR 0010's §14 components 4–6 (supervisor, gate engine, sandboxed runner) plus its §2 checkpoint/resume are exactly a LangGraph graph: typed state channels, conditional edges, `interrupt()`, and a checkpointer. Building this from scratch duplicates a mature runtime; adopting LangGraph gets it for free. The risk is obvious and named by ADR 0010 **C1**: an adopted framework must be a *pattern in its lane*, never the org brain.

## Decision

**Adopt LangGraph as the execution substrate for DGO-X Phases 2–3, mapping the DGO-X model onto it — and bind it under C1–C6.** Mapping: `scripts/dgox/state.py:graph_state` → LangGraph state channels (with the same per-field write authority); AADL/PR gates → conditional edges + `interrupt()` (human approval); each worker node → a Claude Agent SDK dispatch (ADR 0034); checkpoint/resume → the ADR 0023 run-model. Binding invariants:

### LG-1 — Substrate under DGO-X; the board is truth (C1/C2)
LangGraph executes; it does not decide what is true. `board/tickets/*.md` stays canonical and `graph_state` stays its mirror; the LangGraph state is a *projection* of `graph_state`, and any divergence resolves to the board. LangGraph is never the top-level source of truth, and no DasLab law moves into it.

### LG-2 — Gates are edges/interrupts; never dispatch past an open gate (C4)
Each AADL predecessor gate is a conditional edge; a ticket behind an open gate is not routed to a worker node. Security/release/budget and every never-auto-approve category are `interrupt()` points that **halt and wait for the Founder** (QONUN-5); a GATE-5-open deployment stays machine-blocked.

### LG-3 — Workers never write routing fields (C3)
`assignee`/`reviewer`/`routing_reason`/`confidence` are supervisor-only. A worker node edits only its ticket body/log and its work artifacts, matching the ADR 0011 Routing-group invariant.

### LG-4 — One source of durable truth; flag-on == flag-off
LangGraph checkpoints **reconcile with**, never fork, the ADR 0023 run-model and the ADR 0031/0032 attestation + wave-ledger. The graph runs post-decision mechanics through `run_wave` (ADR 0031), so ADR 0025's flag-on==flag-off dispatch equivalence holds; the event store stays the audit system-of-record.

### LG-5 — Phased, feature-flagged, shadow before drive
LangGraph lands behind the `dgox_emit` flag family (ADR 0019), mirrors/enforces before it drives (DGO-X phase discipline), and `/daslab-cycle` remains the fallback until the board approves autonomous drive (C5). It does **not** re-open the ADR 0009 transport ceiling — the Agent SDK runner (ADR 0034) is the admission layer.

## Consequences

**Positive:** DasLab gets the durable, conditional-routing, human-interruptible, resumable loop — the "Devin brain" — as governed substrate, without hand-building or maintaining a bespoke engine. Checkpointing/resume and interrupts compose cleanly with the run-model and never-auto-approve law.

**Negative / accepted:** More architecture surface and a real dependency on LangGraph's runtime semantics; a mapping layer (`graph_state` ⇄ LangGraph state) to keep faithful. Accepted and bounded by the phasing (shadow-first) and by C2 (board wins divergence). If LangGraph's model ever fights DGO-X's, DGO-X wins and the mapping absorbs it.

**Law check:** **C1–C6 (ADR 0010)** apply verbatim — this ADR is reviewed against them. **AADL** (LG-2 makes gates executable edges/interrupts). **ArcRift/board audit** (LG-4 keeps the event store canonical). **LAW 8 / ADR 0009** (not re-opened; ADR 0034 is the gateway). **Model allocation** (nodes dispatch explicit `model` via ADR 0034). **Project placement** (platform code under `scripts/dgox/`; hosts no project content — C6).

## Enforcement / acceptance

- **Ratified by the CTO on 2026-07-24** (RACI 3.1/3.6 A); Security Lead consulted on the sandboxed worker runner + secrets. LG-1…LG-5 judged sound against **ADR 0010 C1–C6** (applied verbatim): **LG-1/C1+C2** — LangGraph is bound as *substrate*, an execution projection of `graph_state` which is itself a mirror of the canonical `board/tickets/*.md`; it is explicitly **never the top-level source of truth / org brain**, no DasLab law moves into it, and any divergence resolves to the board; **LG-2/C4** — every AADL predecessor gate plus each never-auto-approve category is a conditional edge / `interrupt()` that halts and waits for the Founder (a GATE-5-open deployment stays machine-blocked), so no worker node is ever routed past an open gate; **LG-3/C3** — routing fields (`assignee`/`reviewer`/`routing_reason`/`confidence`) stay supervisor-only, a worker node edits only its ticket body/log + artifacts; **LG-4** — checkpoints reconcile with the **ADR 0023** run-model and the **ADR 0031/0032** attestation + wave-ledger, never fork a second durable truth, and the graph runs post-decision mechanics through `run_wave` so **ADR 0025**'s flag-on==flag-off dispatch equivalence holds and the event store stays the audit system-of-record; **LG-5/C5** — LangGraph lands behind `dgox_emit` (ADR 0019, default OFF), mirrors/enforces before it drives, and `/daslab-cycle` stays the fallback until the board approves autonomous drive, with the **ADR 0034** Agent SDK runner as the sole node-execution admission layer (the ADR 0009 transport ceiling is not re-opened). The E2B/OpenHands per-task sandbox is treated as **optional, in-tenant admission infra**, not a source of truth. The **C1/C2 "is LangGraph the brain?" check answers NO** — no LangGraph state can become the top-level dispatcher; DGO-X wins any model conflict and the mapping absorbs it. No defect found; `Proposed` → `Accepted` on this sign-off. **Extends ADR 0010.**
- A LangGraph-substrate PR is reviewed against LG-1…LG-5 **and** ADR 0010 C1–C6; a PR that treats LangGraph state as truth (LG-1/C2), lets a worker write routing (LG-3/C3), routes past an open gate (LG-2/C4), or ships autonomous drive before board approval (LG-5/C5) is rejected.
- Lands behind `dgox_emit` (ADR 0019, default OFF); Phase-2/3 tickets take their own deltas and may not skip predecessor phases.
- Any future "what runs the DGO-X graph / is LangGraph the brain?" question resolves here — the answer to the second is **no**.
