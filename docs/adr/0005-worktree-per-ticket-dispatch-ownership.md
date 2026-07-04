# ADR 0005 — Worktree-per-ticket dispatch ownership

- **Status:** Proposed (authored by Backend EM; **CTO ratifies — GATE-2 / RACI 3.1 A**)
- **Date:** 2026-06-19
- **Scope:** Platform / orchestration
- **Deciders:** Backend EM (author/MGR), **CTO (accountable)**; Security Lead (consulted)
- **Relates:** ADR 0006 (cache prefix), 0008 (memory loop), 0009 (transport limit)
- **Supersedes:** nothing

## Context

The documented baseline (2026-06-15) measured **real code concurrency ≈ 1 per repo** even
though the harness can run many subagents in parallel. The structural cause (current-state
§8): without isolation, concurrent coding agents fight over **one working tree** and
corrupt branch history, so the safe degenerate behaviour is "one coding agent at a time."
This is the primary concurrency unlock (1/repo → ≥ 6 parallel).

**Verified evidence (DRY_RUN, STEP 0.e):** git-worktree isolation is the **full isolation
tier** for this programme. The operator (Founder, 2026-06-19) decided **NO Docker** —
container/microVM hard-isolation is **dropped**; worktrees-only is the isolation tier.
microVM/Firecracker is Linux/KVM-only and was never a local host machine option. So worktrees are
not a stepping-stone to containers here — they are the committed isolation boundary.

Today's dispatch path does **not** create a worktree per ticket. Role-agent prompts tell
each agent to use a worktree, but ownership is ambiguous: if every agent self-creates and
self-cleans, two agents can race on the same path, an agent that crashes leaves a zombie
worktree, and there is no single component responsible for `git worktree prune`. The
repo already shows this drift — `git worktree list` has stale `.claude/worktrees/DAS-1156`,
`DAS-1184`, `DAS-1237`, `DAS-1240` entries from past runs that were never reaped.

## Decision

**The orchestrator owns the worktree lifecycle, not the role agent.** Worktree
create/assign/clean is a **dispatch-layer responsibility** (`/daslab-cycle` /
`/daslab-run`), executed deterministically per ticket.

1. **Create, at dispatch time, by the orchestrator.** When a ticket is selected for a wave
   and is a *code-touching* ticket, the orchestrator creates a fresh worktree off
   **fresh `origin/main`** on the ticket's branch before spawning the agent:
   `git worktree add <path> -b feat/<ticket-slug> origin/main` (LAW 5: one issue = one
   branch = one PR, off fresh `origin/main`).
2. **Deterministic, collision-free path.** Path is a pure function of the ticket id —
   canonical location `\.claude/worktrees/<TICKET-ID>` (matches the existing convention).
   One ticket → one path → no two agents on the same tree. This is the mechanical
   enforcement of **LAW 6** (correctness guard) at the filesystem layer, complementing the
   admission-time same-zone guard.
3. **The agent works only inside its assigned worktree.** The role agent receives the
   worktree path, does its one step there, pushes its branch, opens its PR. It does **not**
   create or delete worktrees — that removes the self-create race entirely.
4. **Deterministic cleanup + zombie reaping by the orchestrator.** On ticket resolution
   (PR merged, or ticket abandoned/blocked), the orchestrator removes the worktree
   (`git worktree remove`) and runs `git worktree prune`. A reap pass at wave start
   removes worktrees whose branch is merged or whose ticket is `done`, so a crashed agent
   never leaves an accumulating zombie (the stale `.claude/worktrees/*` entries above are
   exactly the failure this closes).
5. **Non-code tickets skip the worktree.** Pure-doc / planning / governance tickets that
   only append to the board or write a single additive doc do not need an isolated tree;
   the orchestrator may run them in the main checkout when zone-disjoint (the rule
   is "isolate anything that produces a branch/PR").

**Sandbox boundary.** This ADR is the *full* isolation tier for the current programme. The
known limit — worktrees share the host FS/env, so environment pollution and local I/O cap
*clean* concurrency — is **accepted**, and is the explicit motivation for a future
container-sandbox layer, which the operator **dropped** for now. If a future
operator re-enables Docker, the Sandbox-Manager wraps (does not replace) this worktree
ownership: `allocate(repo,ticket) → {worktree, container}`.

## Consequences

**Positive:** real N-way coding concurrency with deterministic, race-free isolation;
zombie worktrees are reaped, not accumulated; LAW 5 and LAW 6 are enforced mechanically at
the dispatch layer instead of trusted to each agent; a crashed agent is recoverable (its
worktree is reclaimable state, not corrupted shared history).

**Negative / accepted:** worktrees share the host filesystem and environment — no
process/network/resource isolation between concurrent agents (container-level isolation is
deliberately out of scope). Each worktree is a full checkout, costing disk; the reap pass bounds the count.
Heavy concurrent builds remain **RAM-bound** on the host machine (24 GB RAM) (~4–7 heavy builds before
thrash) — so "≥ 6 parallel" is reachable for light/doc work but may be **CAPPED-by-RAM**
on a build-heavy wave; that ceiling is recorded honestly, not hidden.

**Law check:** LAW 1 (engine zone — dispatch code under `scripts/`/`.claude/`); LAW 5
(branch off fresh `origin/main`, never `main`, one PR); LAW 6 (path = f(ticket) enforces
one-tree-per-ticket; the same-zone admission guard remains the *logical* layer above this
*physical* layer). No raw LLM transport is introduced — consistent with ADR 0009.

## Enforcement / acceptance

- The orchestrator implementation makes the orchestrator create/assign/reap worktrees; an
  induced ≥6-ticket parallel wave produces ≥6 isolated branches/PRs with **zero
  branch/FS collision** and deterministic cleanup (no leftover `.claude/worktrees/*`).
- A reap pass at wave start prunes merged/abandoned worktrees (regression test: seed a
  stale worktree, confirm it is gone after one wave).
