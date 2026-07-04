# ADR 0011 — DGO-X Phase-1 data contracts: `graph_state`, the event store, the board adapter, and the shadow-mode rule

- **Status:** Accepted (authored by Backend EM; **CTO ratified — GATE-1+2 / RACI 3.1 A, architecture RACI 3.6 A — 2026-06-20**; Security Lead consulted on event-store contents, context contract, and secrets policy)
- **Date:** 2026-06-20
- **Scope:** Platform / orchestration — DGO-X Phase 1 (graph state + event store), **design only**
- **Deciders:** Backend EM (author/MGR), **CTO (accountable)**; Security Lead (consulted — event-store contents, context contract, secrets policy)
- **Relates:** parent adoption ADR [0010](0010-adopt-dgox-graph-orchestrated-control-plane.md);
  the non-blocking memory loop [0008](0008-nonblocking-arcrift-memory-loop.md)
  (the event-store gitignore/outbox pattern this reuses) and worktree ownership
  [0005](0005-worktree-per-ticket-dispatch-ownership.md); the transport ceiling
  [0009](0009-harness-owns-transport-admission-layer.md)
- **Supersedes:** nothing — first data-contract ADR of the DGO-X set

> This ADR specifies the **Phase-1 data contracts only**. Phase 1 implements them **later, in
> SHADOW mode**: it emits events and mirrors state but changes **no
> dispatch behaviour** — `/daslab-cycle` is unaffected. These are designs the implementation
> tickets (DAS-1376+) build against, not running code shipped by this docs PR. The phasing and
> the binding "What Not To Do" constraints (C1–C6) live in ADR 0010.

## Context

ADR 0010 adopts DGO-X and fixes Phase 1 as "graph state + event store" — the **substrate** the
deterministic supervisor (P2), sandboxed worker (P3), and observability (P4) all stand on.
Phase 1 has one job: make every ticket representable as **typed machine-readable state** and
make every state transition an **append-only event**, while changing nothing the operator
sees. Three contracts realise that, plus one rule that keeps it safe:

1. **`graph_state`** — the typed mirror of a ticket's lifecycle/routing/execution/risk/
   artifact/memory state, with invariants and a single declared writer per field group.
2. **The event store** — the append-only audit system of record (one event per routing/tool/
   gate/approval/run change), JSONL-first, gitignored like the other `board/.*` runtime state.
3. **The board adapter** — read / normalize / write-mirror between `board/tickets/*.md`
   (canonical) and `graph_state` (mirror).
4. **The shadow-mode rule** — Phase 1 emits + mirrors but does not route, gate, or dispatch.

The board stays canonical (ADR 0010 C2). `graph_state` is never the primary record; on any
divergence the board wins. These contracts are deliberately **format-first** (typed fields +
JSONL) so they can be implemented in plain Python with no new service, matching the
file-board runtime; the report's later SQLite/Postgres option (§7.3) is a P4+ scaling choice,
not a Phase-1 dependency.

## Decision

### 1. `graph_state` — typed schema, one writer per group, hard invariants

`graph_state` is a typed record **per ticket** (keyed by `ticket_id`), grouped as follows. Each group has **one declared writer**; no other component may write that group.
The invariants are **enforced at write time** (a write that violates one is rejected and
evented as a violation, not silently applied). In Phase-1 shadow mode these writes are computed
and mirrored but do not feed dispatch.

| Field group | Example fields | **Sole writer** | **Invariant (enforced at write)** |
|---|---|---|---|
| **Identity** | `ticket_id`, `goal`, `parent`, `project`, `dept` | Board adapter | Must match ticket frontmatter exactly (board is canonical; adapter never invents identity). |
| **Lifecycle** | `aadl_stage`, `gate_status`, `predecessor_gate` | Gate engine | **Cannot skip a stage** — `aadl_stage` advances only to the immediate successor, and only when `predecessor_gate` is closed (GATE-5 unreachable while GATE-4 open; ADR 0010 C4). |
| **Routing** | `assignee`, `reviewer`, `routing_reason`, `confidence` | **Supervisor only** | **Role cannot self-route** — a worker/role agent may never write this group (ADR 0010 C3); `reviewer ≠ author` (never self-review). |
| **Execution** | `run_id`, `workspace_id`, `branch`, `pr_url` | Dispatch runner / PR bot | **One ticket → one active branch** (ADR 0005 / Git law); `run_id` correlates the run across events, CI, and ticket log. |
| **Risk** | `severity`, `security_class`, `approval_required` | Gate engine / Security | **Severity is up-only without review** — `severity` may increase autonomously but may only be *lowered* by an explicit security/gate review event (no silent de-escalation). |
| **Artifacts** | `files_changed`, `docs_changed`, `test_results`, `trace_ids` | Worker / CI adapters | Implementation and docs are **co-updated when required** (a code change that needs a doc change records both, or records why not); `trace_ids` link to events. |
| **Memory** | `recall_id`, `store_id`, `memory_scope` | ArcRift adapter | **Scope is flat** — `memory_scope ∈ {daslab, daslab-<project>}`, **no slash** (ADR 0008 / LAW 4); recall + store attempts are recorded, or an explicit `tool_unavailable` event is. |

**Cross-group rules (Phase-1 normaliser):**
- The board adapter populates **Identity** from frontmatter and **nothing else** — it never
  writes Routing/Lifecycle/Risk. This is the structural guarantee behind ADR 0010 C2/C3.
- A field outside its writer's group is a **rejected write → `state_violation` event**. In
  shadow mode this is *observed and logged* (it tells us where today's flow would violate an
  invariant) but does not block anything.
- `graph_state` is **derived**, not authored: it is always reconstructable by re-reading the
  board + replaying the event store. It holds no truth the board + events don't already hold.

### 2. The append-only event store — JSONL-first, one event per change

**Format.** JSONL — one JSON object per line, append-only, **never edited or truncated in
place** (a correction is a new compensating event, mirroring the ADR README "append-only"
discipline). One file in the existing `board/` runtime-state style.

**Location + gitignore (the established pattern).** The event store is **runtime state**, like
`board/.wave-log` and `board/.arcrift-outbox.jsonl` (ADR 0008) — it is **gitignored**, not
tracked. Phase-1 implementation adds to `.gitignore`, beside the existing entries:

```gitignore
# DGO-X event store (append-only runtime audit log — ADR 0011, Phase 1)
board/.events.jsonl
```

(That line is part of *this contract* but is added by the Phase-1 implementation ticket, not by
this additive docs PR.) Like the outbox, the store is durable across waves and machine-readable;
unlike the ticket log it is not operator-facing prose. A future SQLite/Postgres backing may replace the JSONL file at P4+ **without changing these event shapes** — the shapes,
not the storage, are the contract.

**One event per change.** Exactly one append per **routing**, **tool**, **gate**, **approval**,
or **run** change. Every event carries at minimum `event_type`, `ticket_id`, a `created_at` ISO
timestamp, and (where a run exists) `run_id` for correlation. The two load-bearing shapes are
fixed below; gate/approval/run/tool events follow the same envelope and are detailed at their
phase (gate/approval = P2, tool/run = P3), but the **envelope** (`event_type` + `ticket_id` +
`created_at` + correlation id) is fixed now.

**Shape A — `routing_decision`.** Emitted by the supervisor for every dispatch
candidate. **In Phase-1 shadow mode this is emitted but does not cause dispatch** — it records
what the supervisor *would* decide, so P2 can be validated against real shadow data before it is
allowed to drive:

```json
{
  "event_type": "routing_decision",
  "ticket_id": "DAS-1234",
  "from_status": "todo",
  "to_status": "in_progress",
  "assignee": "backend-eng-1",
  "model": "sonnet",
  "reason": "Stage 3 backend implementation; Backend EM owns review.",
  "confidence": 0.91,
  "policy_checks": ["aadl_predecessor_gate_closed", "repo_area_available", "role_authorized"],
  "fallback": "block_and_escalate_to_backend-em",
  "created_at": "2026-06-20T00:00:00Z"
}
```

Notes binding the shape to the laws: `assignee`/`reason`/`confidence` are **supervisor-authored**
(never a worker — C3); `model` is **explicit** (LAW 3 / ADR 0007, never inferred from
frontmatter — claude-code#44385); `policy_checks` are the gate-engine preflight that must all
pass before P2 would dispatch (`aadl_predecessor_gate_closed` is C4; `repo_area_available` is
the LAW 6 same-zone guard from ADR 0009; `role_authorized` is RACI); `fallback` is the
deterministic action if a check fails (block + escalate to the author's manager per ROUTING).

**Shape B — `agent_invocation`.** Recorded when a role agent is dispatched
(P2/P3 onward; in shadow mode the *intended* invocation is recorded without launching):

| Field | Purpose | Law tie |
|---|---|---|
| `run_id` | correlates one dispatched run across logs, events, traces, CI, ticket log | the join key for all observability (P4) |
| `ticket_id` | work-item identity | board is canonical (C2) |
| `role_key` | `.claude/agents/<role>.md`-compatible role | RACI role identity |
| `model` | explicit model dispatch | LAW 3 / ADR 0007 (explicit, provider-abstracted) |
| `workspace_id` | sandbox / worktree identity | ADR 0005 worktree = f(ticket); P3 sandbox wraps it |
| `context_contract` | minimal task context — **never raw full org state** | prompt-injection control; Security-consulted |
| `allowed_tools` | tool allowlist **by task class** | least privilege; worker-overreach control |
| `secrets_policy` | **no secrets by default**; short-lived scoped creds only when gate-approved | secret-exposure control; Security-consulted |
| `exit_contract` | required: ticket log entry, artifacts, test evidence, **memory store result** | board audit law + ADR 0008 store-at-end (or explicit `tool_unavailable`) |

### 3. The board adapter — read / normalize / write-mirror contract

The board adapter is the **only** bridge between `board/tickets/*.md` (canonical operator-facing
truth, ADR 0010 C2) and `graph_state` (machine-readable mirror). Three operations:

1. **READ** — parse each `tickets/DAS-*.md` (frontmatter + `## Log`): `id`, `title`, `status`,
   `assignee`, `author`, `dept`, `priority`, `parent`, `goal`, `created`, `updated`. The
   resolver follows the board rule that `DAS-12` resolves to `tickets/DAS-12-*.md`.
2. **NORMALIZE** — project frontmatter into the typed `graph_state` **Identity** group, and
   reconcile Lifecycle/Routing/Execution from the ticket's current `status`/`assignee` plus the
   replayed event store. The adapter writes **only the Identity group**; all other groups are
   owned by their respective writers (§1). Normalisation is **pure** — same board + same event
   log ⇒ same `graph_state` (deterministic, replayable).
3. **WRITE-MIRROR** — `graph_state` mirrors the board **one way by default**: board → state.
   Phase 1 does **not** write back to ticket files. A future phase that mirrors state → board
   (e.g. an evented status change reflected into frontmatter) does so **only** as today's roles
   do — an appended `## Log` entry, never a silent frontmatter edit (board audit law) — and
   **routing fields remain orchestrator/supervisor-written**, never worker-written (C3).
   **Divergence rule:** if `graph_state` and the board disagree, the **board wins** and the
   adapter emits a `mirror_divergence` event; the mirror is rebuilt from the board, never the
   reverse. The board is never "corrected" to match the mirror.

### 4. The SHADOW-mode rule (Phase 1's safety boundary)

**Phase 1 emits events and mirrors `graph_state`, but changes NO dispatch behaviour.**
Concretely:

- `/daslab-cycle` (and `/daslab-run`) remain the **only** behaviour-affecting dispatch path and
  are **unaffected** — same triage, same waves, same output. DGO-X Phase 1 runs *alongside*
  them, observing.
- The supervisor's `routing_decision` events are **advisory shadow records** — they describe
  what P2 *would* route; **nothing dispatches off them** in Phase 1.
- The gate engine's invariant checks run as **observers**: a would-be violation is recorded as a
  `state_violation`/`mirror_divergence` event for analysis; **nothing is blocked or refused**
  yet (refusal is P2, behind its own flag and its own ADR delta).
- No write-back to ticket files (§3.3); the board is read-only from DGO-X's side in Phase 1.
- **Exit criterion for Phase 1 → Phase 2:** shadow events demonstrate the supervisor's routing
  and the gate engine's invariants match the human-run board decisions on real waves (coverage
  + agreement measured from the event store) **before** P2 is permitted to *drive*. This is how
  ADR 0010's "DGO-X may observe before it drives" is made concrete and falsifiable.

This rule is the mechanical guarantee that adopting DGO-X (ADR 0010) cannot regress the running
org: Phase 1 is **pure observation + mirroring**, reversible by turning off one feature flag.

## Consequences

**Positive:** after Phase 1, every ticket has a typed, replayable `graph_state` and every
transition is an append-only event — the audit system of record previously identified as missing,
delivered **without touching dispatch**. Because `graph_state` is *derived* (board +
event replay) and the store is append-only JSONL in the existing `board/.*` runtime-state
pattern, Phase 1 needs **no new service, no database, no schema migration** — plain Python over
files, matching the runtime. The shadow `routing_decision`/gate events become the **evidence
base** that lets P2 (the supervisor + gate engine) be validated against real human decisions
before it is ever allowed to route — de-risking the whole migration.

**Negative / accepted:** Phase 1 adds a **second representation** of work state (`graph_state`)
that must stay consistent with the board — accepted because the consistency rule is one-way and
explicit (board wins; divergence is evented; mirror is rebuilt, never the board), so the mirror
can never corrupt the canonical record (ADR 0010 C2). The JSONL store **grows unbounded** and is
**gitignored** (runtime state, not history) — accepted, matching `.arcrift-outbox.jsonl`;
rotation/compaction and any SQLite/Postgres backing are a P4+ concern and explicitly out of
Phase-1 scope, and must preserve these event shapes. The event store **may contain sensitive
routing/tool context**, so its contents are **Security-Lead-consulted** (context contract,
secrets policy): `secrets_policy` defaults to no-secrets, `context_contract` is
minimal (never raw full org state), and the store is gitignored so it is never pushed.

**Law check:** **Board audit** (board stays canonical; no silent frontmatter edits — any future
write-back is an appended `## Log` entry; the event store *strengthens* the audit trail).
**Charter/RACI** (`reviewer ≠ author`; Routing group is supervisor-only — C3). **AADL** (Lifecycle
"cannot skip stage" + `predecessor_gate` closed — C4). **Git law** (Execution "one ticket → one
active branch" — ADR 0005). **ArcRift/LAW 4** (Memory scope flat, no slash; store-at-end or
explicit `tool_unavailable` — ADR 0008). **Model allocation/LAW 3** (`model` explicit in every
`routing_decision`/`agent_invocation`, provider-abstracted — ADR 0007). **LAW 8** (no transport
proxy introduced — the model field records the admission-layer decision per ADR 0009; nothing
here sits on the HTTP transport). **Project placement** (no project artifacts written; these are
platform docs under `docs/` — ADR 0010 C6).

## Enforcement / acceptance (handed to the Phase-1 implementation tickets, DAS-1376+)

- **CTO ratifies** this design (GATE-1+2, RACI 3.1/3.6) together with ADR 0010; `Proposed`
  until sign-off, then `Accepted`. Security Lead is **consulted** on the event-store contents,
  context contract, and secrets policy.
- Phase-1 implementation (DAS-1376+) builds: the `graph_state` typed schema with per-group
  writer enforcement and the §1 invariants (violations → `state_violation` events); the
  append-only `board/.events.jsonl` writer (+ the `.gitignore` entry above) emitting at least
  `routing_decision` (Shape A) on real waves; the board adapter read/normalize/one-way-mirror
  (Identity-only writes; `mirror_divergence` on disagreement, board wins); all under the
  **shadow-mode flag** with `/daslab-cycle` **provably unaffected** (same dispatch output
  with the flag on vs. off).
- **Acceptance is "shadow-clean":** on an induced multi-ticket wave, Phase 1 emits a
  `routing_decision` for 100% of dispatched tickets and mirrors
  `graph_state` for every ticket, while a diff of the wave's *actual* dispatch with the flag
  on vs. off is **empty** (no behaviour change). The shadow agreement/coverage numbers are the
  Phase-1 → Phase-2 gate.
- This ADR is the citation any future "what is the Phase-1 graph_state / event / board-adapter
  contract?" question resolves to.

---

> **Amended by [ADR-0025](0025-events-load-bearing.md) (2026-07-03) — appended,
> not edited in place.** §4 **The SHADOW-mode rule** ("the supervisor's
> `routing_decision` events are **advisory shadow records** — nothing dispatches off
> them") is **narrowed** by ADR-0025: `board/.events.jsonl` is **load-bearing** as a
> producer substrate (the emitter/checkpoints light up the T-gates) and as the
> **operator-invoked `--resume`/`--fork` recovery reader** (DAS-1445). §4 holds
> **verbatim for every normal `/daslab-cycle` / `/daslab-run` wave** (flag-on ==
> flag-off); the explicit operator-recovery path is the one sanctioned reader, and it
> is failure-isolated and gated by the same committed-evidence T-gates. See ADR-0025
> parts (a)–(c) for the full narrowed invariant.
