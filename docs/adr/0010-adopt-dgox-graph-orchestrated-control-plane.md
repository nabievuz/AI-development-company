# ADR 0010 — Adopt DGO-X: a graph-orchestrated, gate-driven DasLab control plane

- **Status:** Accepted (authored by Backend EM; **CTO ratified — GATE-1+2 / RACI 3.1 A, architecture RACI 3.6 A — 2026-06-20**; Security Lead consulted per §10)
- **Date:** 2026-06-20
- **Scope:** Platform / orchestration — the target runtime architecture
- **Deciders:** Backend EM (author/MGR), **CTO (accountable)**; Security Lead (consulted — event store, context contract, secrets policy); CEO (operator-blessed the variant)
- **Relates:** Companion data-contracts ADR
  [0011](0011-dgox-phase-1-data-contracts.md) (Phase-1 design); prior platform design set
  [0005](0005-worktree-per-ticket-dispatch-ownership.md)/[0006](0006-static-cache-prefix-layout.md)/[0007](0007-model-retier-cascade-boundary.md)/[0008](0008-nonblocking-arcrift-memory-loop.md)/[0009](0009-harness-owns-transport-admission-layer.md)
- **Supersedes:** nothing — establishes DGO-X fresh; it *extends* the file-based board model, does not replace it

> This is the **architecture-adoption ADR** that ratifies *what* DasLab is
> evolving toward (the §14 decision) and fixes the *order* and the *guardrails* of the
> migration. The concrete Phase-1 data contracts are designed in the companion ADR 0011; the
> later phases each take their own implementation tickets and ADR deltas. DGO-X is **phased
> and feature-flagged** — nothing here changes dispatch behaviour on merge.

## Context

DasLab today is a repo-root Claude Code session driving `board/tickets/*.md`,
`.claude/agents/*`, and the `/daslab-plan` → `/daslab-cycle` → `/daslab-run` skills. The
ADR 0005–0009 set made parallel dispatch *correct* (worktree-per-ticket
isolation, static cache prefix, model re-tier boundary, non-blocking memory loop) and wrote
down the load-bearing ceiling (0009: under the harness, LAW 8 is an admission layer, not a
transport proxy). What that prior set deliberately left open is the **structural** gap the
operator's architecture review names: routing logic is implicit in skill/prompt code,
failed runs are not deterministically resumable, the audit trail is a human ticket log rather
than a machine-readable event stream, sandbox isolation is worktree-only, and AADL/PR gates
are documented but not enforced by a typed engine.

The operator commissioned a weighted SWOT across six candidate architectures (report §4–6) and
**committed to Variant C — DGO-X Hybrid** (464/500, normalized 92.8%; runner-up Current
DasLab++ at 76.8%). DGO-X is *not* "adopt a multi-agent framework." It keeps every DasLab law
(charter, RACI, AADL, Git law, ArcRift memory law, model allocation, board audit, project
placement) and the operator-facing file board as canonical truth, and **adds** a deterministic
graph-orchestration control plane on top. The board, the 32-role org, and `/daslab-cycle`
survive; the control plane reads and mirrors them.

This ADR ratifies that decision and designs Phase 1 only (ADR 0011). The CTO ratifies; Backend EM does not self-ratify (RACI 3.1 / 3.6).

**Citation correction (binding).** The report (§6.3) writes that DGO-X "turns *ADR-0003* graph
control plane into practical runtime." **That citation is wrong.** ADR
[0003](0003-self-locating-root.md) is *self-locating repository root* — it has nothing to do
with a graph control plane. There is **no prior "graph control plane" ADR**; DGO-X is
**established fresh here in ADR 0010.** Any future reference to "the DasLab graph control-plane
decision" resolves to this ADR, not 0003.

## Decision

**Adopt DGO-X as DasLab's target runtime — phased, feature-flagged, board-as-truth.**
DGO-X preserves the file-based board and role-subagent model and **adds**, on top of it
(report §14): typed `graph_state`, deterministic supervisor routing, an append-only event
store, checkpoint/resume, policy/gate enforcement in code, sandboxed worker execution, an
explicit model gateway, an ArcRift memory adapter, and CI/PR observability.

### 1. The nine added components (the §14 decision, as the target architecture)

| # | Component | Responsibility | Lands in phase |
|---|---|---|---|
| 1 | **Typed `graph_state`** | machine-readable mirror of each ticket's lifecycle/routing/execution/risk/artifact/memory state, with invariants | P1 (designed in ADR 0011) |
| 2 | **Append-only event store** | audit system of record: one event per routing/tool/gate/approval/run change | P1 (designed in ADR 0011) |
| 3 | **Board adapter** | read/normalize/write-mirror between `board/tickets/*.md` (canonical) and `graph_state` | P1 (designed in ADR 0011) |
| 4 | **Deterministic supervisor** | candidate selection + routing (priority, role availability, same-zone guard, confidence gate) — *replaces implicit prompt-logic routing* | P2 |
| 5 | **Gate engine** | enforces AADL predecessor gates, PR/CI requirements, self-review prevention, security/release/budget approval interrupts — *refuses invalid transitions* | P2 |
| 6 | **Sandboxed worker runner** | policy-controlled workspace isolation (OpenHands-style) wrapping the ADR-0005 worktree/branch/PR law; ACI tool layer; tool transcripts as events | P3 |
| 7 | **Model gateway** | explicit model per dispatch, provider abstraction (LAW 3) — *the in-orchestrator admission layer of ADR 0009, not a transport proxy* | P2 (admission) / P3 |
| 8 | **ArcRift memory adapter** | recall-at-start / store-at-end / prune, strict flat project scope (ADR 0008, LAW 4) | P1 contract / wired through |
| 9 | **CI/PR observability** | link CI runs, test summaries, security scans to ticket/run IDs; gate-report + cost/latency metrics | P4 |
| (opt) | **Event-triggered scheduler** | move from manual-only waves to safe event-triggered cycles, behind a per-task-class flag, watchdog + dead-letter queue, board-approved | **P5 — optional, last** |

### 2. Checkpoint/resume and the model-gateway boundary

- **Checkpoint/resume** is a first-class control-plane capability (LangGraph-style
  persistence): every agent run gets a start/end checkpoint so a failed run resumes from
  deterministic state rather than re-running from scratch. Designed alongside the event store
  (its checkpoints are events); proven at P2/P3 scale.
- **The model gateway is the in-orchestrator admission layer, not a transport proxy.** This is
  the load-bearing boundary from ADR [0009](0009-harness-owns-transport-admission-layer.md):
  under the Claude Code harness, DasLab does **not** own the LLM transport, so the gateway
  governs *what is dispatched and with which model* (admission, priority, same-zone guard,
  per-dispatch budget) — it does **not** sit on the raw HTTP transport. The literal
  "transparent proxy / no un-proxied call" form is achievable **only** under a future SDK-based
  runner and remains future work gated by its own ADR. DGO-X inherits 0009's ceiling verbatim;
  it does not re-open it.

### 3. Phased + feature-flagged; `/daslab-cycle` is the fallback until Phase 5 is board-approved

Each phase ships behind a feature flag and is **additive**. The manual operator-invoked
`/daslab-cycle` remains the **only** behaviour-affecting dispatch entrypoint and the
**fallback** through Phases 1–4. DGO-X may *observe, mirror, and enforce* before it *drives*:

- **Phase 1 runs in SHADOW mode** — it emits events and mirrors `graph_state` but changes **no
  dispatch behaviour** (see ADR 0011). `/daslab-cycle` is unaffected.
- **Phases 2–4** add refusal of invalid transitions, sandboxing, and observability — still
  operator-invoked, no autonomous scheduling.
- **Phase 5 (autonomous event-triggered scheduling) is OPTIONAL and LAST**, and may not ship
  until graph-state, event store, and approval interrupts are reliable **and the board
  explicitly approves** autonomous production scheduling (report §13; binding constraint C5
  below). Until then, `/daslab-cycle` stays the manual override.

### 4. Phase order (the §12 roadmap, made binding)

DGO-X migrates in the report's **§12 phase order**: the **reactive / event-triggered
scheduler moves from first to LAST (Phase 5) and becomes OPTIONAL.** The reasoning is the
§13 constraint "no background scheduler before graph-state, event store, and approval
interrupts are reliable" — you cannot safely schedule autonomously before the state, audit, and
human-approval substrate exists. Phase order is therefore:

| DGO-X phase | Goal | Note |
|---|---|---|
| **P0 — Stabilize the runtime** | board stays reliable while DGO-X is built; "tool-unavailable" event pattern; no new scheduler | precondition |
| **P1 — Graph state + event store** | every ticket representable as typed state; every transition evented; board adapter mirror; `routing_decision` emitted **without changing behaviour** | **state & audit FIRST** |
| **P2 — Deterministic supervisor + gate engine** | runtime can **refuse** invalid transitions; AADL predecessor-gate checks; same-zone guard; self-review prevention; approval interrupts for security/release/budget | supervisor encodes the routing that was implicit in skill logic |
| **P3 — Sandboxed worker runner** | informal worktree-only isolation → policy-controlled workspace; ACI tool layer; tool transcripts as events; **preserves ADR-0005 branch/worktree/PR law** | wraps ADR 0005, does not supersede it |
| **P4 — CI/gate observability** | review decisions depend on **evidence, not trust**; CI/test/scan linked to ticket/run IDs; gate-report generator; cost/latency per ticket; dashboards | closes the audit loop the event store opened |
| **P5 — OPTIONAL event-triggered scheduler** | manual-only waves → safe event-triggered cycles, **board-approved**; per-task-class flag; watchdog + dead-letter queue; `/daslab-cycle` stays manual override | **reactive scheduler moved from first → last**; gated behind P1–P4 and explicit board approval |

This table fixes the **dependency order and the reactive-scheduler demotion to P5** as the binding migration sequence.

### 5. The §13 "What Not To Do" — BINDING constraints

These are not advice; they are **enforced invariants** of DGO-X. Violating one is a design
defect, not a style choice. (Cross-checked against the binding-constraints table, report §2.)

- **C1 — Do not replace DasLab with a generic multi-agent demo framework**, and do not make
  OpenHands, MetaGPT, ChatDev, DevOpsGPT, Aider, or SWE-agent the **top-level source of truth**.
  Each is adopted only as a *pattern* in its lane (sandbox / SOP artifacts / worker ACI), never
  as the org brain. (report §13, §1, §5)
- **C2 — Do not bypass `board/tickets/*.md`.** The board remains the operator-facing canonical
  truth; `graph_state` is a machine-readable **mirror**, never the primary record. A divergence
  is resolved in the board's favour. (report §13; ADR 0011 board-adapter contract)
- **C3 — Worker agents NEVER write routing fields.** `assignee`/`reviewer`/`routing_reason`/
  `confidence` are **supervisor-only**; a worker edits only its own ticket body/log and the
  artifacts of its work (matches the board concurrency rule and ADR 0011's `graph_state`
  Routing-group invariant "role cannot self-route"). (report §13, §8.1, §10 "worker overreach")
- **C4 — Do not dispatch ahead of AADL gates.** A ticket whose predecessor AADL gate is open is
  not dispatched; GATE-5 cannot pass while GATE-4 is open; the gate engine enforces this in code
  at P2. (report §13, §9.3; CLAUDE.md AADL law)
- **C5 — No background scheduler before graph-state, event store, and approval interrupts are
  reliable.** This is the load-bearing reason the reactive scheduler is demoted to P5/optional and
  requires explicit **board approval** before autonomous production scheduling. (report §13,
  §12 Phase 5)
- **C6 — Project-specific artifacts stay under `projects/<project>/` only.** Platform-level
  architecture docs (this ADR, the report) are the *only* exception and live under `docs/`. No
  DGO-X component may write product/project content outside its project folder. (report §13;
  CLAUDE.md project placement law)

A future "why does DGO-X forbid X?" question resolves to this list.

## Consequences

**Positive:** DasLab becomes **replayable** (checkpoint/resume), **auditable** (every route,
gate, approval, model call, tool call, CI result is an event), **enforceable** (the gate engine
refuses invalid transitions instead of trusting prompts), **safer** (sandboxed workers, secrets
policy, context contract), and **measurable** (cost per accepted ticket, gate pass rate, rework
rate, mean-time-to-review — report §11). Crucially this is gained **without losing** the board,
the 32-role org, RACI, AADL, or the manual `/daslab-cycle` operator control — they are
preserved and mirrored, not replaced. The migration is incremental: each phase is shippable,
flag-gated, and falls back to today's runtime.

**Negative / accepted:** DGO-X is **more architecture surface** than the file board — it
requires adapters (board, ArcRift, git, CI, sandbox, approvals) and careful cost/latency
control (report §6.3 weaknesses). The honest mitigations: (a) **overengineering risk** is bound
by the phasing — P1 is *shadow-only*, nothing ships autonomous until P5 and board approval; (b)
**stale-topology / mis-routing risk** is bound by C2 (board is truth, divergence resolves to
the board) and the supervisor's deterministic, evented routing decisions; (c) the **transport
proxy is NOT delivered** — the model gateway is the admission layer per ADR 0009, and the
literal "no un-proxied call" guarantee stays explicitly future SDK-runner work. We adopt the
*target* here; we do not claim any phase beyond P1 is implemented by this ADR.

**Law check:** **Charter / RACI** (Backend EM authors, CTO ratifies — this ADR is `Proposed`
until CTO sign-off; architecture is RACI 3.6 CTO-accountable). **AADL** (C4 makes
predecessor-gate enforcement a binding invariant; the gate engine is the runtime form of the
AADL law). **Board audit** (C2/C3 keep the board canonical and silent-edit-free; the event
store *strengthens* the audit law with a machine-readable trail). **Git law** (ADR 0005's one
issue = one branch = one PR survives; P3 sandbox **wraps** it). **ArcRift memory law** (the
adapter preserves ADR 0008's non-blocking recall/store with flat project scope). **Model
allocation** (the gateway dispatches explicit `model`, provider-abstracted, LAW 3; gate/
architecture/security stay opus per ADR 0007). **LAW 2 (no hollow gate)** (C4 + the gate engine
make AADL/PR gates *enforced*, not documented; we do not claim the transport proxy we cannot
yet build). **LAW 8** (inherited from ADR 0009 verbatim — admission, not transport, on the
harness). **Project placement** (C6).

## Enforcement / acceptance

- **This ADR is ratified by the CTO** (GATE-1+2, RACI 3.1/3.6). It is `Proposed` until that
  sign-off, then `Accepted`. Security Lead is **consulted** on the event store, context
  contract, and secrets policy (report §10).
- **Phase 1 is designed in ADR [0011](0011-dgox-phase-1-data-contracts.md)** (graph_state
  schema, event store, board adapter, shadow-mode rule). The §12 phase order and the
  reactive-scheduler demotion (§Decision.4) are the **binding migration sequence**; later phases take their
  own tickets + ADR deltas and may not skip ahead of their predecessor (C4 applies to the
  migration itself).
- **The §13 "What Not To Do" (C1–C6)** are binding invariants any DGO-X PR is reviewed against;
  a PR that lets a worker write a routing field (C3), bypasses the board (C2), dispatches ahead
  of an AADL gate (C4), or ships a scheduler before the substrate + board approval (C5) is
  rejected on principle.
- **On merge**, Phase-1 implementation tickets are opened and flipped actionable by the orchestrator.
- This ADR is the citation any future "what is DGO-X / why this order / why not 0003?" question
  resolves to.

---

> **Amended by [ADR-0025](0025-events-load-bearing.md) (2026-07-03) — appended,
> not edited in place.** §5 **C3**'s framing of the event store as an *advisory-only
> shadow record* ("nothing dispatches off them") is **narrowed** by ADR-0025: the
> DGO-X event store is **load-bearing** as a producer substrate and as the
> **operator-invoked `--resume`/`--fork` recovery reader**. The "no dispatch behaviour
> change / flag-on == flag-off" guarantee is preserved **for normal `/daslab-cycle`
> waves** and only there; the operator-recovery path is the sanctioned exception, and
> a producer *writing* the store is not "dispatching off" it. C3's "workers never write
> routing fields" rule is unchanged. See ADR-0025 for the narrowed invariant and how
> determinism/anti-gaming is now guaranteed (committed evidence P13 + immutable T7 + R-9).
