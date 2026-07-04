# ADR 0008 — Non-blocking ArcRift memory loop

- **Status:** Proposed (authored by Backend EM; **CTO ratifies — GATE-2 / RACI 3.1 A**)
- **Date:** 2026-06-19
- **Scope:** Platform / memory subsystem
- **Deciders:** Backend EM (author/MGR), **CTO (accountable)**; Security Lead (consulted — no cross-project memory bleed)
- **Relates:** `CLAUDE.md` QONUN ArcRift law; ADR 0005/0006/0007/0009

## Context

LAW 4 (QONUN) mandates `recall_context` at task start and `store_memory` at task close for
every agent. These calls sit **on the critical path**: every agent blocks on a recall before
it can start and on a store before it finishes. ArcRift's graph-extraction step (routed
through the sonnet claude-bridge) adds latency to the store path specifically (confirmed in
ArcRift memory: "graph extraction latency PART_OF ArcRift").

The audit's finding that memory sits on the critical path is treated as **ground truth**.
The async-memory *speedup figures* from recent un-peer-reviewed preprints are
simulation-derived — we adopt the **pattern** (memory off the critical path) and **prove
the latency delta on our own bench**; we do **not** cite the preprint numbers as guarantees.

**The hard constraint (LAW 4):** making memory async **must not drop a required store.**
A naive fire-and-forget that loses a store on a crash silently violates LAW 4. The known
`store_memory` concurrency race (recorded in user memory) makes this sharper: concurrent
stores must not corrupt or lose each other.

## Decision

**One prewarmed recall per wave + fire-and-forget store backed by a durable outbox.**
Memory leaves the agent critical path without ever silently dropping a required store.

1. **One prewarmed recall per wave (not per agent).** The orchestrator issues a single
   `recall_context(project=…, prompt=<wave context>)` at wave start and passes the returned
   `<ARCRIFT_retrieved_context>` to the wave's agents. Per-agent blocking recalls collapse
   to one prewarmed read. The recall output is **dynamic content** → it lives in the
   **dynamic tail after the last cache breakpoint** (ADR 0006 §3), never in the cached
   prefix.
   - *Project scoping stays strict (LAW 4 + Security Lead):* `project="daslab"` for org-
     level, `project="daslab-<slug>"` for a specific project. The prewarmed recall is
     scoped to the wave's project; a wave spanning projects prewarms per project — **never**
     mixes one project's memory into another's prompt.
2. **`store_memory` is fire-and-forget via a durable outbox.** An agent's close-of-task
   store is **enqueued to a durable local outbox** (append-only file / local SQLite — **no
   new service**; keep it local) and the agent returns immediately. A background
   drainer performs the actual `store_memory` MCP call and **retries on failure** until it
   lands.
3. **Durability contract (LAW 4 — the load-bearing rule):**
   > *A required store is enqueued durably before the agent reports done; the drainer
   > retries until it lands. A store is never dropped on a crash — on restart the drainer
   > replays the unacked outbox.* Fire-and-forget removes the store from the *latency*
   > path, **not** from the *durability* guarantee.
4. **Concurrency-race safety.** The outbox is the single serialization point: stores are
   appended (append is atomic) and the drainer applies them **one at a time** (or with the
   MCP's documented safe concurrency), which **closes the known `store_memory` race** —
   concurrent agents enqueue independently; the drainer, not the agents, talks to ArcRift.
5. **Kill-switch / drain on shutdown.** On orchestrator stop, the drainer **flushes the
   outbox before exit** (or leaves it durable for replay) — shutdown never abandons pending
   required stores.

## Consequences

**Positive:** recall collapses N blocking reads → 1 prewarmed read per wave; store latency
leaves the agent critical path entirely; the durable outbox makes LAW 4
*stronger* than the synchronous status quo (a crash mid-store today loses it; the outbox
replays it); the single-drainer design closes the concurrency race.

**Negative / accepted:** memory is now **eventually** consistent — a just-stored fact may
not be recallable for the few seconds until the drainer lands it (acceptable: recall is
prewarmed per *wave*, and within-wave agents do not depend on a sibling's not-yet-stored
fact). The outbox is **new local durable state** to manage (size-bound + replay on
restart); it is a file/SQLite, **not** a new paid service, so $0 infra cost.

**Law check:** LAW 4 (recall at start / store at close preserved; **zero dropped stores**
via outbox + retry; strict project scoping — no cross-project bleed); LAW 1 (memory-loop
code under engine zones; outbox is local engine state, not under `projects/`). No new LLM
transport — the bridge/MCP path is unchanged; consistent with ADR 0009.

## Enforcement / acceptance

- One prewarmed recall per wave; store enqueued to a durable outbox + background drainer
  with retry.
- **Fault-injection test (LAW 4):** kill the store mid-flight (or crash the drainer) → the
  store still lands on replay; **0 dropped stores** in the test.
- Median memory-call latency demonstrably **off** the agent critical path (measured via
  benchmarking); project-scoping isolation verified (no `daslab-<a>` fact recalled into a
  `daslab-<b>` prompt).
