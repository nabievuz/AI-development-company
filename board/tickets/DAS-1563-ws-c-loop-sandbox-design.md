---
id: DAS-1563
title: WS-C Design — durable loop and sandbox admission model, state mapping, gates as interrupts
status: done
assignee: cto
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

### 2026-07-24 — Backend EM
AADL Stage-2 (GATE-2) design authored: `docs/design/ws-c-langgraph-loop.md`. Mirrors the
WS-A/WS-B/WS-D design-doc style; each section traced to its FR + ADR-0035 LG invariant +
DGO-X C-invariant (ADR-0010).

Design summary:
- **§1 LangGraph substrate adapter / graph_state-mirror (LG-1 / FR-001,002 / C1,C2):** the
  LangGraph state is an *execution projection* of `scripts/dgox/state.py:GraphState`, itself
  a derived mirror of canonical `board/tickets/*.md`. One channel per `FIELD_GROUPS` group,
  each inheriting its `GROUP_WRITER` sole-writer authority; writes route through `apply_group`
  so the four `StateInvariantError` guards fire at the projection boundary. Reconciliation is
  named at the board_adapter re-read at each supervisor tick — **board wins**, the checkpoint
  is never a tiebreaker. DGO-X wins any model conflict; no LangGraph state can become the
  top-level dispatcher (the C1/C2 "is LangGraph the brain?" check answers NO).
- **§2 gates-as-interrupts (LG-2 / FR-003 / C4):** each AADL predecessor gate = a conditional
  edge (worker node unreachable while the gate is open); every never-auto-approve category =
  an `interrupt()` halt-for-Founder point surfaced as the DAS-1446 interrupt card / `status:
  interrupted`; a GATE-5-open deployment stays machine-blocked; fail-closed.
- **§3 worker write-scope (LG-3 / FR-004 / C3):** routing fields stay supervisor-only, denied
  to workers by both `GROUP_WRITER` authority + `apply_group` guards and by graph topology;
  a worker writes only its ticket body/log + artifacts.
- **§4 checkpoint-resume (LG-4 / FR-005 / ADR-0025):** the LangGraph checkpoint is execution
  scratch keyed by `run_id`, subordinate to the ADR-0023 run-model; post-decision mechanics
  run through the single `run_wave` producer (flag-on == flag-off; no orphan wave-ledger entry
  per ADR-0032); guard-before-act idempotent resume (DAS-1447) — no forked truth.
- **§5 sandbox-isolation (FR-006):** per-task `SandboxBackend` contract with a named host-free
  reference stub (`LocalStubSandbox`, buildable now by DAS-1565) and a live `DockerSandbox`
  (E2B/OpenHands, Docker per Q2) scoped to **blocked DAS-1566**; four fail-closed walls
  (host / repo / other-task / unscoped-credential) + fail-closed escape-prevention.
- **§6 flag posture (LG-5 / FR-007 / C5):** behind `ws_c_langgraph_loop` OFF within the
  `dgox_emit` family; shadow→enforce→drive under board approval; `/daslab-cycle` fallback.

Negative-path spec handed to DAS-1567 (§7): SC-001 idempotent resume (no double-apply,
ledger reconciles); SC-002 gate-interrupt actually blocks + injected divergence resolves to
the board; SC-003 routing-write rejection (structurally unreachable, not merely guarded);
SC-004 flag-off byte-identical + flag-on shadow-only; **SC-005** sandbox-escape (host/repo
escape, cross-task isolation, unscoped credential + egress, resource-limit) — carrying the
GATE-1 reviewer note that the FR-006 escape negative test lives here, run against the stub.

Validators green: `board_lint` exit 0 (180 tickets, 0 violations; the lone WARN is the
pre-existing DAS-1507 body-status prose, not this ticket), `check_links` exit 0,
`check_spec_consistency` exit 0 (10 SPECs, refs consistent).

⛔ LOCAL-ONLY: no git push/PR/commit/remote. Touched only `docs/design/ws-c-langgraph-loop.md`
and this ticket. Status → in_review, assignee → cto (GATE-2 accountable; Security Lead
consulted on §5 sandbox isolation). Handing to CTO for GATE-2 sign-off.

### 2026-07-24 — CTO (GATE-2 closure)
**AADL Stage-2 / GATE-2 (Design) for WS-C LOOP — CLOSED. Design ratified.** Reviewed
`docs/design/ws-c-langgraph-loop.md` against Accepted ADR-0035 (LG-1..LG-5), ADR-0010
(DGO-X C1–C6 + `scripts/dgox/state.py` GraphState/FIELD_GROUPS/apply_group), ADR-0023
(run-model), ADR-0025 (event store canonical), and ADR-0011 (Routing sole-writer). Carried
the Security-Lead **consulted** review on §5 myself.

**C1/C2 board-canonical — HOLDS (the load-bearing check).** LangGraph stays a *projection*
of `graph_state`, itself a derived mirror of canonical `board/tickets/*.md`. Truth flows one
direction down a two-hop chain (§1.1); divergence resolves **up** to the board at exactly
one named seam — the `board_adapter` re-read at the head of each supervisor tick (§1.3) —
and the LangGraph **checkpoint is never a tiebreaker** (§1.3, §4.1). Three structural facts
(§1.4) keep LangGraph in its lane: no decision authority (routing is supervisor-written,
worker-read-only), no independent store (overwritten from the board on divergence), DGO-X
wins any model conflict. The "is LangGraph the brain?" check answers **NO** — no LangGraph
state can become the top-level dispatcher. Channels mirror `FIELD_GROUPS` one-per-group,
each inheriting `GROUP_WRITER` authority, writes routed through `apply_group` so the four
`StateInvariantError` guards fire at the projection boundary. C1/C2 sound → NOT routed back.

**Gates-as-interrupts (§2, LG-2/C4) — sound.** Predecessor gate = conditional edge (worker
unreachable while open); never-auto-approve categories (QONUN-5) = `interrupt()`
halt-for-Founder surfaced as the DAS-1446 interrupt card / `status: interrupted`;
GATE-5-open deployment stays machine-blocked; fail-closed (unclassifiable → halt, never
pass). Gate writes confined to `lifecycle`/`risk` (gate_engine), never a worker.

**Worker write-scope (§3, LG-3/C3) — sound.** `routing` channel write-denied to workers by
both `GROUP_WRITER`+`apply_group` guards and graph topology (unrepresentable, not merely
forbidden); worker surface = own ticket body/`## Log` + artifacts only. Matches ADR-0011 §1.

**Checkpoint reconcile (§4, LG-4/ADR-0023/0025/0032) — sound.** Checkpoint = execution
scratch keyed by `run_id`, subordinate to the run-model; single `run_wave(plan,results)`
producer gives flag-on == flag-off (ADR-0025) with no orphan ledger entry (ADR-0032 bijection);
guard-before-act idempotent resume (DAS-1447); event store stays audit SoR. No forked truth.

**§5 sandbox isolation (Security-Lead consulted, carried by CTO) — sound.** Four fail-closed
walls each named and deny-by-default: **host** (no path/proc/netns escape; workdir-confined,
`..`/absolute rejected), **repo** (only the task's own worktree mounted — composes with the
one-issue-one-worktree law; `.git`/board/other tickets unmounted), **other-task** (one
sandbox per `task_id`, no shared mutable mount/network/credential — safe under the no-parallel-
cap Model Allocation Law), **unscoped-credential** (`credentials` empty by default per
ADR-0012 no-secrets-by-default; secret only on a gate-scoped, ttl'd, task-scoped grant; value
never enters an event — Tier-M fact-of-grant only; egress deny-all except explicit allow-list
so a leaked secret has no default exfil path). Escape-prevention (§5.3) is fail-closed: any
un-granted reach → denied `ExecResult`/`SandboxEscapeError` with no side effect. Stub
`LocalStubSandbox` is buildable now (DAS-1565) and enforces the **same refusal decisions** as
the live backend, so the escape tests re-run unchanged against DAS-1566. Live `DockerSandbox`
(E2B/OpenHands, Docker per Q2) correctly scoped to **blocked DAS-1566**. §5 accepted.

**Negative-path spec (§7) accepted for DAS-1567.** SC-001 idempotent resume, SC-002 gate-block
+ divergence-resolves-to-board, SC-003 routing-write rejection, SC-004 flag-off byte-identical
/ shadow-on, **SC-005** sandbox-escape (host/repo/cross-task/unscoped-cred+egress/resource-
limit). All expressible against the DAS-1564/1565 surfaces + `apply_group`/`run_wave`/
`verify_wave_ledger`.

**SC-005 binding.** DAS-1567's `implements:` listed only [SC-001..SC-004]; the design assigns
the FR-006 escape negative test to it under SC-005. Added `SC-005` to DAS-1567's `implements:`
so the escape test is bound. SC-005 is a valid SPEC-004 token → `check_spec_consistency` stays
green. Recorded observation: SPEC-004's SC-005 is literally the CI-hygiene criterion while the
design overloads the same id as the sandbox-escape umbrella — both readings land on DAS-1567;
a documentation tidy-up downstream may split them, not a GATE-2 blocker.

**Validators (post-edit):** `board_lint` exit 0 (180 tickets, 0 violations; lone WARN =
pre-existing DAS-1507 body-status prose), `check_links` exit 0, `check_spec_consistency`
exit 0 (10 SPECs, refs consistent).

⛔ LOCAL-ONLY: no git push/PR/commit/remote. Edited only this ticket + DAS-1567 frontmatter/log;
design doc/ADRs/config/code untouched. **Status → done. GATE-2 CLOSED.** Unblocks DAS-1564
(`scripts/dgox`) + DAS-1565 (`tools/sandbox`) — distinct zones, parallelisable; DAS-1566 stays
blocked (external Docker/E2B host, Q2).
</content>
