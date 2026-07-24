# WS-C durable-loop + sandbox design — LangGraph as a `graph_state` projection under DGO-X, gates as interrupts, checkpoint reconcile, per-task sandbox isolation

- **Status:** Design (AADL Stage 2 — GATE-2) — awaiting review (CTO accountable; Security Lead consulted)
- **Date:** 2026-07-24
- **Ticket:** DAS-1563 (WS-C Design); epic DAS-1561 (MUSTAQIL WS-C LOOP)
- **Author:** Backend EM (responsible); CTO (accountable stage owner); Security Lead (consulted — per-task sandbox isolation + escape prevention + scoped credentials)
- **Binds to:** [ADR-0035](../adr/0035-langgraph-dgox-execution-substrate.md) (LG-1…LG-5, Accepted 2026-07-24, under DGO-X C1–C6), [`docs/specs/004-mustaqil-ws-c-loop/SPEC.md`](../specs/004-mustaqil-ws-c-loop/SPEC.md) (FR-001…FR-007, SC-001…SC-005, reviewed), [ADR-0010](../adr/0010-adopt-dgox-graph-orchestrated-control-plane.md) (DGO-X target + C1–C6 + `graph_state`), [ADR-0023](../adr/0023-run-model.md) (run-model: `run_id`/ULID, `board/runs/`, wave checkpoints), [ADR-0025](../adr/0025-events-load-bearing.md) (event store load-bearing; flag-on == flag-off dispatch), [ADR-0031](../adr/0031-wave-runner-attestation.md)/[ADR-0032](../adr/0032-harness-forced-attestation.md) (`run_wave` attestation + wave-ledger), [ADR-0034](../adr/0034-agent-sdk-headless-runner.md) (the Agent SDK runner = the sole node-execution admission layer), [ADR-0011](../adr/0011-dgox-phase-1-data-contracts.md) (Routing-group sole-writer invariant), Founder discovery answers Q2 (Docker-based E2B/OpenHands on the tenant VM) and Q4 (supervised until the first proof, then shadow before drive)
- **Downstream:** DAS-1564 (LangGraph substrate adapter, `zone: scripts/dgox`), DAS-1565 (E2B/OpenHands per-task sandbox adapter + **stub backend**, `zone: tools/sandbox`), DAS-1566 (**blocked** — live-host sandbox wiring + isolation smoke, external dependency Q2), DAS-1567 (negative/resume tests — this doc hands it §7, `zone: tests`), DAS-1568 (deploy runbook + flag posture), DAS-1569 (maintenance / health-eval)

> **Scope of this doc.** WHAT the governed execution model is and HOW its pieces
> interlock — the `graph_state` ⇄ LangGraph channel projection (with per-field
> write authority), the gate-as-interrupt contract, the worker write-scope
> invariant, the checkpoint-reconcile rule, the per-task sandbox isolation
> contract, the feature-flag posture, and the negative-path spec the Testing
> ticket implements. It ships **no runtime code**: the LangGraph adapter under
> `scripts/dgox/`, the sandbox adapter under `tools/sandbox/`, and the tests are
> built by DAS-1564/1565/1567 against this design. Interface signatures below are
> **contracts, not implementations**. `scripts/dgox/state.py:GraphState` +
> `apply_group` (Phase-1 shipped) is the reference this design projects onto
> LangGraph — cited, not modified here. This ticket touches only `docs/design/`
> + the ticket file.

## 0. The loop under DGO-X (one picture)

LangGraph is the **executing substrate**; it is never the source of truth. The
board is truth, `graph_state` is its mirror, and the LangGraph state is an
**execution projection** of `graph_state`. Truth flows down; a divergence
resolves **up** to the board.

```
   board/tickets/*.md            ← CANONICAL TRUTH (C2). Only edit path: status
        │  (the SSOT)              transition + ## Log; supervisor owns routing.
        ▼  board_adapter (re-read + event replay — ADR-0011/0023)
   scripts/dgox/state.py:GraphState   ← DERIVED MIRROR (never primary; state.py docstring)
        │  per-field write authority = FIELD_GROUPS / GROUP_WRITER (ADR-0011 §1)
        ▼  substrate adapter (DAS-1564) — PROJECTION, one direction
   LangGraph state channels          ← EXECUTION PROJECTION (LG-1/C1). Never the
        │                              top-level dispatcher; DGO-X wins conflicts.
        ▼
   ┌─ supervisor node ──▶ conditional edge (AADL gate closed?) ──┐
   │                                │ open gate                   │
   │                          interrupt() ── HALT, wait Founder ──┘  (LG-2/C4)
   │                                │ closed gate
   │                                ▼
   │   worker node  ── dispatch via Agent SDK (ADR-0034) ──▶ per-task SANDBOX
   │        │  edits ONLY ticket body/log + artifacts (LG-3/C3)   (E2B/OpenHands,
   │        │  NEVER a routing field                               Docker, Q2)
   │        ▼
   └─ checkpointer ─▶ run_wave(plan, results) ─▶ ADR-0023 run-model + ADR-0031/0032
            (reconcile, never fork — LG-4)        attestation + wave-ledger; event
                                                  store stays audit SoR (ADR-0025)

   ALL of the above behind ws_c_langgraph_loop OFF (default) + dgox_emit family:
   SHADOW (mirror/enforce) before DRIVE — /daslab-cycle is the fallback (LG-5/C5).
```

- **[LG-1 / FR-001,002 / C1,C2]** — §1. The LangGraph state is a projection of
  `graph_state`, itself a mirror of the board. Board wins any divergence; no
  LangGraph state can become the top-level dispatcher.
- **[LG-2 / FR-003 / C4]** — §2. Every AADL predecessor gate is a conditional
  edge; security / budget / never-auto-approve categories are `interrupt()`
  points that halt for the Founder. No node is routed past an open gate.
- **[LG-3 / FR-004 / C3]** — §3. A worker node edits only its ticket body/log +
  artifacts; routing fields stay supervisor-only.
- **[LG-4 / FR-005]** — §4. Checkpoints reconcile with the ADR-0023 run-model and
  the ADR-0031/0032 ledger through `run_wave`; no forked truth; flag-on ==
  flag-off (ADR-0025); resume is idempotent (DAS-1447).
- **[LG-5 / FR-006 sandbox]** — §5. Each worker's code/command execution runs in
  an isolated per-task sandbox; untrusted execution cannot reach the host, the
  repo, another task, or an unscoped credential.
- **[LG-5 / FR-007 / C5]** — §6. Behind `ws_c_langgraph_loop` OFF + the
  `dgox_emit` shadow family; shadow before drive; `/daslab-cycle` is the fallback.

`graph_state` throughout means `scripts/dgox/state.py:GraphState` (the Phase-1
typed mirror). The **substrate adapter** is the new `scripts/dgox/` module
(DAS-1564) that projects `graph_state` onto LangGraph state channels; the
**sandbox adapter** is the new `tools/sandbox/` module (DAS-1565).

---

## 1. LangGraph substrate adapter — the graph state is a projection of `graph_state` (LG-1 / FR-001 + FR-002 / C1 + C2)

**Requirement (FR-001 / LG-1):** provide a durable plan-act-observe-replan loop
as the DGO-X Phase-2/3 execution substrate, with checkpoint and resume,
**consuming LangGraph as a governed substrate that is never the top-level source
of truth**. **(FR-002 / LG-1 / C2):** the graph state MUST be a projection /
mirror of `board/tickets/`; any divergence MUST resolve to the board.

### 1.1 Two mirrors, one direction of truth

Truth flows down a two-hop chain, and only down:

1. `board/tickets/*.md` — **canonical** (C2). The `state.py` module docstring
   already fixes this: `graph_state` "is a DERIVED mirror, reconstructable by
   re-reading the board … plus replaying the event store. It is NEVER primary
   truth — on any divergence the board wins."
2. `graph_state` (`GraphState`) — the derived mirror of a single ticket.
3. **LangGraph state channels** — an **execution projection** of `graph_state`,
   introduced by this design. The LangGraph state exists only to *run* the loop;
   it holds no fact the board does not already hold.

The adapter is a **projection function**, not a second store. It reads
`graph_state` (which the board adapter has already reconciled to the board) and
materialises LangGraph channels; it never writes a fact *back* into `graph_state`
that did not originate from the board/event path.

### 1.2 Channel schema — one channel per `graph_state` field group, same write authority

The LangGraph state schema mirrors `FIELD_GROUPS` **exactly**, one channel per
group, and each channel inherits the group's sole writer from `GROUP_WRITER`
(ADR-0011 §1). The channel is not a free-form dict — a write to it routes through
`apply_group`, so the four `StateInvariantError` guards (cannot-skip-AADL-stage,
role-cannot-self-route, severity-up-only, flat-ArcRift-scope) fire at the
projection boundary exactly as they do in `graph_state`:

| LangGraph channel | `graph_state` group | Sole writer node (`GROUP_WRITER`) | Contents |
|---|---|---|---|
| `identity` | identity | `board_adapter` | `ticket_id, goal, parent, project, dept` |
| `lifecycle` | lifecycle | `gate_engine` | `aadl_stage, gate_status, predecessor_gate` |
| `routing` | routing | `supervisor` | `assignee, reviewer, routing_reason, confidence` — **worker-read-only** (§3) |
| `execution` | execution | `dispatch_runner` | `run_id, workspace_id, branch, pr_url` |
| `risk` | risk | `gate_engine_or_security` | `severity, security_class, approval_required` |
| `artifacts` | artifacts | `worker_or_ci` | `files_changed, docs_changed, test_results, trace_ids` |
| `memory` | memory | `arcrift_adapter` | `recall_id, store_id, memory_scope` |

**Adapter contract (projection shape; no runtime code shipped here):**

```python
# scripts/dgox — substrate adapter contract (DAS-1564 builds it; behind ws_c_langgraph_loop OFF)
def project(state: GraphState) -> LangGraphState:
    """graph_state -> LangGraph channels. ONE direction. Read-only over the board."""

def reconcile(lg: LangGraphState, board_state: GraphState) -> GraphState:
    """On any divergence, the BOARD value wins (C2). Returns the board-derived
    GraphState; the LangGraph channel is overwritten from it, never vice-versa.
    Emits a state_violation / reconciliation event (ADR-0011) for the audit trail."""
```

### 1.3 Where reconciliation happens — board wins, always

Divergence is resolved at exactly one named seam: the **board_adapter re-read**
at the head of each supervisor tick (the `identity`/board-truth refresh). The
adapter re-derives `graph_state` from `board/tickets/*.md` + event replay
(ADR-0023 reconstruction), then `reconcile()` overwrites any LangGraph channel
that disagrees with the board-derived value. The LangGraph checkpoint is **not**
consulted as a tiebreaker — it is execution scratch, not truth (§4). This is the
C2 rule made mechanical: *the board is read last and wins.*

### 1.4 LangGraph can never become the top-level dispatcher (C1 / C2)

Three structural facts keep LangGraph in its lane (the ADR-0010 C1/C2 "is
LangGraph the brain?" check answers **NO**):

- **No decision authority.** The graph executes edges; it does not decide
  *what is true* or *what should be dispatched*. Routing (`assignee`, order,
  reviewer) is written only by the supervisor into the `routing` channel and is
  **read-only** to every worker node (§3). LangGraph selecting the *next edge* is
  execution, not routing.
- **No independent store.** The graph holds no fact the board does not hold; on
  divergence it is overwritten from the board (§1.3). A "LangGraph-state-as-truth"
  PR is rejected against LG-1/C2 (ADR-0035 enforcement).
- **DGO-X wins model conflicts.** If LangGraph's runtime semantics ever fight the
  DGO-X model, DGO-X wins and the mapping (§1.2) absorbs it — the ADR-0035
  accepted-negative. There is no code path where a LangGraph channel value
  becomes the top-level dispatcher's input without first passing the board
  re-read.

### 1.5 Shadow before drive (LG-5, tie to §6)

Behind `ws_c_langgraph_loop` OFF the projection is computed but **does not drive**
dispatch — it mirrors and (in the enforce sub-phase) validates against
`/daslab-cycle`'s decisions without acting on them. Only after the board approves
autonomous drive (Q4: supervised until the first proof, then shadow before drive)
does the projected graph drive a wave. See §6.

**Trace:** two-hop projection (board → `graph_state` → LangGraph channels), one
direction; per-channel write authority = `GROUP_WRITER`; reconciliation at the
board_adapter re-read with the board winning; no dispatcher role for LangGraph —
closes **FR-001 + FR-002 / LG-1 / C1 + C2**.

---

## 2. Gates as conditional edges / interrupts (LG-2 / FR-003 / C4)

**Requirement (FR-003 / LG-2 / C4):** each AADL predecessor gate, and every
security / budget / never-auto-approve category, MUST be an interrupt or
conditional-edge point that halts and waits for the Founder; a ticket behind an
open gate MUST NOT be routed to a worker node.

### 2.1 AADL predecessor gate = conditional edge

The `lifecycle` channel already carries `aadl_stage`, `gate_status`, and
`predecessor_gate`, and `apply_group` already refuses to advance a stage unless
`predecessor_gate == closed` (`_check_aadl_stage`). The substrate lifts that
invariant into a **conditional edge** before any worker node:

```
supervisor ──▶ [conditional edge: predecessor_gate closed?]
                   │ closed  ─────────────▶ worker node (dispatch)
                   │ open    ─────────────▶ interrupt()  (HALT, no dispatch)
```

The edge predicate reads only `graph_state.predecessor_gate` (board-derived,
§1.3). A worker node is **unreachable** while the gate is open — there is no edge
from an open-gate supervisor state to a worker node. This is the graph-level
analogue of the `cannot_skip_aadl_stage` write guard: the guard blocks the
*state write*, the edge blocks the *routing*.

### 2.2 Never-auto-approve categories = `interrupt()` halt-for-Founder points

Security, release/deployment, budget, and every never-auto-approve category
(QONUN-5: `new_goal`, `security_sensitive`, `schema_migration`,
`gate5_deployment`, `governance_or_policy`, `permission_change`, `secret_change`)
become `interrupt()` points. On reaching one the graph **halts and waits for the
Founder** — it does not auto-resolve, does not degrade to a default, does not
route onward:

- A **GATE-5-open deployment stays machine-blocked**: the graph parks at the
  interrupt and no downstream node runs until a Founder approval arrives. This is
  the executable form of "shipping with GATE-5 open is FORBIDDEN".
- The interrupt maps onto the existing board mechanics: the halt is surfaced as
  the DAS-1446 **interrupt card** (`board/interrupts/<id>.json`) and the ticket
  parks at `status: interrupted` — *not* `blocked`, *not* `in_review`. The graph
  resumes only on the Founder's `resume:<value>` (board README lifecycle), and
  the resume is idempotent (§4.3).
- The interrupt is **fail-closed**: an unclassifiable gate/category resolves to
  "halt", never "pass". Losing progress to an over-cautious halt is always
  preferable to routing past an ungoverned gate.

### 2.3 The gate engine is the writer, not the worker

Gate evaluation writes only the `lifecycle`/`risk` channels, whose sole writer is
`gate_engine` / `gate_engine_or_security` (§1.2). A worker node never opens,
closes, or signs a gate — it has no write to those channels (§3). AADL gate order
(`depends_on` / open-gate skips) is unchanged by the substrate's existence; the
substrate makes the *same* order executable rather than prose-enforced.

**Trace:** predecessor gate → conditional edge (worker unreachable while open);
never-auto-approve categories → `interrupt()` halt-for-Founder → interrupt card /
`interrupted`; GATE-5-open stays machine-blocked; fail-closed — closes **FR-003 /
LG-2 / C4**.

---

## 3. Worker write-scope — routing fields stay supervisor-only (LG-3 / FR-004 / C3)

**Requirement (FR-004 / LG-3 / C3):** a worker node MUST edit only its own ticket
body/log and work artifacts; it MUST NOT write any routing field
(`assignee` / `reviewer` / `routing_reason` / `confidence`), which remain
supervisor-only.

### 3.1 The `routing` channel is write-denied to worker nodes

The invariant is enforced at two layers, both structural:

1. **Channel write authority (§1.2).** The `routing` channel's sole writer is
   `supervisor` (`GROUP_WRITER["routing"] == "supervisor"`). A worker node is not
   the supervisor, so a worker's attempt to `apply_group(state, "routing", …)` is
   rejected — `apply_group` also refuses a cross-group field (`wrong_group_writer`
   / `StateInvariantError`) and, for `reviewer`, refuses self-routing
   (`_check_self_route`: `reviewer ≠ author/assignee`). The board-canonical mirror
   of this is ADR-0011 §1 (Routing group, supervisor-only) and matches the WS-A
   C3 tool invariant and the WS-B runner C3.
2. **Graph topology.** No edge grants a worker node a `routing`-channel write
   handle. A worker node's out-edges write only `artifacts` (its `files_changed`,
   `docs_changed`, `test_results`, `trace_ids`) and its ticket body/log. Routing
   is computed by the supervisor node from a *separate* input and never accepts a
   worker-supplied value — the write is unrepresentable, not merely forbidden.

### 3.2 What a worker node MAY touch

A worker node's write surface is exactly: (a) its own ticket **body + `## Log`**
(the board edit discipline — status transition + log entry, never a silent edit;
board README), and (b) its **work artifacts** (code in its worktree, the
`artifacts` channel). It reads the board and other channels but writes only these
two. This is the same "edits only its own ticket file plus the artifacts of its
work" rule the board concurrency section fixes — the substrate does not widen it.

**Trace:** `routing` channel write-denied to workers by both `GROUP_WRITER`
authority + `apply_group` guards and by graph topology; worker write surface =
ticket body/log + artifacts only — closes **FR-004 / LG-3 / C3**.

---

## 4. Checkpoint / resume reconcile — no forked truth, idempotent resume (LG-4 / FR-005 + ADR-0025)

**Requirement (FR-005 / LG-4):** checkpoints MUST reconcile with the ADR-0023
run-model and the ADR-0031/0032 attestation + wave-ledger and MUST NOT fork a
second durable source of truth, so flag-on dispatch is equivalent to flag-off
(ADR-0025). **(SC-001):** resume after a mid-run interruption loses no progress
and does not double-apply a committed side effect (DAS-1447).

### 4.1 The LangGraph checkpointer is execution scratch, not a truth store

LangGraph's checkpointer persists the graph's in-flight execution state (which
node, which channel values, pending interrupts) so a crashed run can resume. This
design pins it as **subordinate** to the ADR-0023 run-model:

- The **durable truth of a run** is the ADR-0023 object: `run_id` (ULID),
  `board/runs/<run_id>/`, the per-wave checkpoints, and the `ledger_hashes`
  chain. The LangGraph checkpoint is keyed **by that same `run_id`** and holds no
  run-fact the run-model does not — it is a resumption index, not a second ledger.
- On resume, the run-model + board are the authority: the graph re-derives
  `graph_state` from the board + event replay (§1.3) and overwrites any LangGraph
  channel that disagrees. A LangGraph checkpoint that diverges from the board
  **loses** — same C2 rule as §1.3. There is therefore **no second durable
  truth** to fork.

### 4.2 Post-decision mechanics run through `run_wave` — flag-on == flag-off

The graph never writes the event/attestation surface itself. Its **only** write
into `board/.events.jsonl` / `metrics/attestations/` / `board/wave-ledger.jsonl`
is **through `scripts/wave_runner.py:run_wave(plan, results)`** — the single
post-decision seam (ADR-0031), exactly as the WS-B runner and `/daslab-cycle` do.
This gives the flag-on == flag-off guarantee at a function boundary (ADR-0025):

- `run_wave` "reads no clock and makes no routing decision" and does "the SAME
  mechanical steps every time" given `(plan, results)`. The graph supplies the
  *same* `(plan, results)` `/daslab-cycle` would, so the committed attestation is
  identical — the event store stays the audit system-of-record.
- The graph adds **no second producer**: it never calls `dispatch_emitter` /
  `pulse_checkpoint` / the ledger appenders directly. A second producer would
  break the ADR-0032 reconciliation bijection (`verify_wave_ledger` — no orphan
  attestations, no chain gap). The substrate is a *client of the decision seam*,
  identical in this respect to WS-B §3.

### 4.3 Idempotent resume (SC-001 / DAS-1447)

Resume must never double-apply a committed side effect (a merge, an event append,
a checkpoint). The design fixes a **guard-before-act** contract at each side
effect, keyed by `run_id` + node identity:

- **Committed side effects are checked before re-application.** On resume, a node
  first asks "did this already commit for this `run_id`?" — a merged PR is
  detected by its merge state, an emitted event by its `run_id`/`trace_ids`
  presence, a written checkpoint by the `board/runs/<run_id>/` marker — and skips
  the re-apply if so (the DAS-1447 guard). The `run_wave` `run_id:` frontmatter
  stamp (`_stamp_wave_run_ids`, idempotent) is the existing analogue.
- **The interrupt/resume path is idempotent by construction.** An `interrupted`
  ticket resumed by the Founder's `resume:<value>` (§2.2) re-enters the wave with
  the answer available; re-running the parked node re-reads the board, finds the
  committed work, and does not re-do it. A paused wave that later runs again is
  safe.
- **No partial-truth window.** Because truth is the board + run-model and the
  LangGraph checkpoint is subordinate (§4.1), a resume can never "believe" a
  half-written checkpoint over the board.

**Trace:** LangGraph checkpoint keyed by `run_id`, subordinate to the ADR-0023
run-model, board wins on resume divergence; post-decision mechanics through the
single `run_wave` producer (flag-on == flag-off, ADR-0025; no orphan ledger
entry, ADR-0032); guard-before-act idempotent resume — closes **FR-005 / LG-4 +
SC-001**.

---

## 5. Per-task sandbox isolation contract (LG-5 / FR-006)

**Requirement (FR-006):** each worker node's code / command execution MUST run
inside an isolated, in-tenant per-task sandbox (E2B / OpenHands, Docker-based per
Q2) such that untrusted execution cannot reach the host, the repo, another task,
or an unscoped credential.

This section is the **isolation + escape-prevention contract** DAS-1565 (stub
adapter) and DAS-1567 (tests) implement. The **live** sandbox needs a real
Docker/E2B host (Q2) and is scoped to the **blocked** DAS-1566 — it is not this
design and not DAS-1565.

### 5.1 The sandbox adapter contract (stub-buildable now)

```python
# tools/sandbox — per-task sandbox adapter contract (DAS-1565 builds it; behind ws_c_langgraph_loop OFF)
class SandboxBackend(Protocol):
    def open(self, *, task_id: str, scope: SandboxScope) -> SandboxHandle: ...
    def exec(self, handle: SandboxHandle, argv: list[str]) -> ExecResult: ...
    def close(self, handle: SandboxHandle) -> None: ...

@dataclass(frozen=True)
class SandboxScope:
    task_id: str                      # one sandbox per task — never shared across tasks
    workdir_mounts: list[Mount]       # ONLY this task's worktree, read/write; nothing else
    egress_profile: str               # deny-all by default; explicit domains only (WS-A §3)
    credentials: list[ScopedSecret]   # EMPTY by default; only gate-approved, ttl'd, task-scoped
    resource_limits: ResourceLimits   # cpu / mem / pids / wallclock caps (fork-bomb + runaway guard)
```

- **STUB / reference backend named:** `LocalStubSandbox` — a buildable,
  host-free backend that satisfies the `SandboxBackend` contract by running
  against a **temporary, per-task working directory** with the mount/egress/
  credential/limit checks enforced in-process (deny-by-default), returning
  deterministic `ExecResult`s. It lets DAS-1565 build and DAS-1567 test the
  **isolation contract** (what is reachable / refused) **without a live host**.
  It is explicitly **not** a security boundary for real untrusted code — it
  proves the *contract shape and the refusal logic*, not kernel-level isolation.
- **LIVE backend (DAS-1566, blocked):** `DockerSandbox` (E2B / OpenHands,
  Docker-based per Q2) provides the real kernel/namespace isolation on the tenant
  VM. It needs a real Docker/E2B host, so the **live-host isolation smoke** is
  DAS-1566's external dependency — named here, not built here.

### 5.2 The isolation boundary — four fail-closed walls

Untrusted execution inside a sandbox is denied, by default, all four of:

1. **Host.** No path out to the host filesystem, host processes, or host
   network namespace. The sandbox is the ADR-0035 "optional, in-tenant admission
   infra" — not a source of truth and not a host shell. The stub enforces this by
   confining every path to the per-task workdir and rejecting absolute/`..`
   escapes; the live backend enforces it by container namespace isolation.
2. **Repo.** A node reaches **only its own task's worktree** (`workdir_mounts`),
   never the whole repo, `.git`, the board, or another ticket's files. This
   composes with the ADR-0005 one-issue-one-worktree law: the worktree *is* the
   sandbox mount, and nothing outside it is mounted.
3. **Another task.** One sandbox per `task_id`; no shared mutable mount, no
   shared network, no shared credential across tasks. Concurrency (no parallel
   cap, Model Allocation Law) is safe because two tasks share **no** sandbox
   surface — the same per-dispatch isolation posture WS-B §6 takes for the runner
   process (env + worktree) applied to the execution sandbox.
4. **Unscoped credential.** `credentials` is **empty by default** (WS-A/ADR-0012
   `no-secrets-by-default`). A secret enters a sandbox only when a gate approval
   scoped it — task-scoped, ttl'd, least-privilege — and the credential value
   never enters an event (fact-of-grant + scope + ttl only, Tier-M). Egress is
   deny-all except an explicit domain allow-list (WS-A §3), so a leaked secret has
   no default exfil path.

### 5.3 Escape-prevention rule (the FR-006 negative surface)

The contract is **fail-closed**: any reach the scope did not explicitly grant is
**refused**, not best-effort allowed. A path outside the workdir mount, a host
egress not on the profile, a credential not in the scoped set, or a resource
request past the limit each returns a denied `ExecResult` (or raises a
`SandboxEscapeError`) and performs **no** side effect. This is the surface
DAS-1567 SC-005 probes (§7). The stub backend implements the *same* refusal
decisions as the live backend so the escape tests pass against the stub and
re-run unchanged against DAS-1566's live host.

**Trace:** per-task `SandboxBackend` contract with a named host-free stub
(`LocalStubSandbox`) + a live `DockerSandbox` scoped to blocked DAS-1566; four
fail-closed walls (host / repo / other-task / unscoped-credential); fail-closed
escape-prevention for SC-005 — closes **FR-006 / LG-5 (sandbox half)**.

---

## 6. Feature-flag / shadow-before-drive posture (LG-5 / FR-007 / C5)

**Requirement (FR-007 / LG-5 / C5):** the substrate MUST be gated by
`ws_c_langgraph_loop`, DEFAULT OFF, shadow-before-drive; adding it MUST change no
dispatch behaviour on merge; `/daslab-cycle` MUST remain the fallback until the
board approves autonomous drive.

- **`ws_c_langgraph_loop: false`** already exists in `config/features.yaml`
  (consumer noted as "the finisher loop"; flip only "when the loop runs a real
  0→100 slice under supervision (Q4)"). It sits within the `dgox_emit` flag family
  (ADR-0035 LG-5 / ADR-0019) — the shadow-emission channel.
- **OFF (default) ⇒ inert.** The substrate does not drive dispatch; a wave through
  `/daslab-cycle` is **byte-identical to pre-merge** (SC-004). Merging the adapter
  adds a *capability*, not a behaviour change.
- **Shadow before drive (Q4 / C5).** With the flag ON the substrate first
  **mirrors** (computes the projection, emits shadow), then **enforces** (validates
  its decisions against `/daslab-cycle` without acting), and only **drives** a real
  wave after the board approves autonomous drive — supervised until the first
  proof lands. `/daslab-cycle` stays the fallback the whole way.
- **Flip is a Founder/board act**, never the substrate's own — the same posture as
  WS-A TB-5 and WS-B SR-5. DAS-1568 (Deployment / GATE-5) owns the runbook and
  keeps the flag OFF on merge; rollback = disabling the key.

**Trace:** `ws_c_langgraph_loop` OFF ⇒ inert + byte-identical interactive waves;
shadow→enforce→drive under board approval; `/daslab-cycle` fallback; Founder-only
flip — closes **FR-007 / LG-5 / C5**.

---

## 7. Negative-path spec for DAS-1567 (Testing / GATE-4)

The behaviours the Testing ticket (DAS-1567, `zone: tests`, `implements:
[SC-001, SC-002, SC-003, SC-004]`, `depends_on: [DAS-1564, DAS-1565]`) must
assert, **plus SC-005** (the GATE-1 reviewer note: FR-006 sandbox-escape negative
test lives here). Each is expressible against the substrate adapter
(`project`/`reconcile`, the gate edge/interrupt), the `apply_group` guards, the
`SandboxBackend` stub, and the existing `run_wave` / `verify_wave_ledger`
primitives, folded into `tests/test_ws_c_langgraph_loop.py`.

### SC-001 — idempotent checkpoint / resume (LG-4 / FR-005)

- **SC-001a — resume loses no progress.** Interrupt a run mid-wave (after a
  committed side effect, before the next node); resume from the LangGraph
  checkpoint keyed by `run_id`; assert the completed work is present and the run
  reaches the same terminal state as an uninterrupted run.
- **SC-001b — no double-apply.** Assert a committed side effect (a merge, an
  emitted event, a written checkpoint) is **not re-applied** on resume — the
  guard-before-act check (§4.3) detects the prior commit by `run_id`/`trace_ids`
  and skips it. Assert the wave-ledger still reconciles
  (`verify_wave_ledger(...)` has no orphan attestation and no chain gap) and that
  `run_wave` remains the **only** producer (parity with a flag-off wave — a second
  direct producer write is a test failure).

### SC-002 — gate-interrupt blocks + divergence resolves to the board (LG-2/LG-1 / FR-003/FR-002)

- **SC-002a — a ticket behind an open gate is not routed to a worker node.** With
  `graph_state.predecessor_gate == open`, assert the conditional edge routes to
  `interrupt()` (HALT) and **no worker node runs** — the worker is unreachable
  while the gate is open (§2.1). Assert a never-auto-approve category (e.g. a
  GATE-5-open deployment) parks at the interrupt and **stays machine-blocked**
  (surfaced as an interrupt card / `status: interrupted`), resuming only on a
  Founder `resume:<value>`.
- **SC-002b — injected graph/board divergence resolves to the board.** Inject a
  LangGraph channel value that disagrees with `board/tickets/`; run the
  board_adapter re-read + `reconcile()`; assert the **board value wins** and the
  LangGraph channel is overwritten from it (§1.3), with a reconciliation/
  `state_violation` event emitted. Assert the LangGraph checkpoint is **not** used
  as a tiebreaker.

### SC-003 — routing-field write rejection (LG-3 / FR-004 / C3)

- **SC-003a — a worker node cannot write a routing field.** Assert a worker
  node's attempt to write the `routing` channel (`assignee` / `reviewer` /
  `routing_reason` / `confidence`) is **rejected** — `apply_group(state,
  "routing", …)` raises `StateInvariantError` (`wrong_group_writer`, or
  `role_cannot_self_route` for a self-`reviewer`), and no `routing` value is
  mutated. Assert the write is structurally unreachable via graph topology (no
  worker out-edge holds a `routing`-channel write handle), not merely guarded.
- **SC-003b — a worker MAY write its own artifacts/log.** Assert the same worker
  node **can** write the `artifacts` channel + its ticket body/`## Log`, so the
  invariant is a scoping rule, not a global freeze.

### SC-004 — flag-off inert / byte-identical wave (LG-5 / FR-007)

- **SC-004a — inert with the flag OFF.** With `ws_c_langgraph_loop` OFF
  (default), assert the substrate does not drive and a wave through
  `/daslab-cycle` is **byte-identical to pre-merge** (no new events, no new
  attestation attributable to the substrate). Merging the adapter changes no
  interactive-wave behaviour.
- **SC-004b — ON runs shadow only.** Assert that flipping the flag ON (in a test
  harness) runs the loop in **shadow** — it mirrors/enforces without driving a
  real dispatch — until an explicit board-approval signal, never auto-driving on
  the flag alone.

### SC-005 — sandbox-escape refusal (FR-006, GATE-1 reviewer note)

Run against the `LocalStubSandbox` (host-free), same refusal decisions the live
`DockerSandbox` (DAS-1566) will enforce:

- **SC-005a — host/repo escape refused.** Assert a node's attempt to read/write a
  path **outside its per-task workdir mount** (an absolute path, a `..` escape,
  `.git`, the board, another ticket's files) is **refused** (denied `ExecResult` /
  `SandboxEscapeError`) and performs no side effect.
- **SC-005b — cross-task isolation.** Assert two concurrent sandboxes keyed by
  different `task_id` share **no** mount, network, or credential — task A cannot
  observe or mutate task B's sandbox.
- **SC-005c — unscoped credential + egress refused.** Assert `credentials` is
  empty by default and a request for a secret **not** in the scoped set is
  refused; assert egress to a host **not** on the explicit allow-list is denied
  (deny-all default), so a leaked secret has no default exfil path.
- **SC-005d — resource-limit guard.** Assert a request past `resource_limits`
  (cpu/mem/pids/wallclock — e.g. a fork-bomb or runaway loop) is capped/refused,
  not allowed to exhaust the host.

**Hand-off:** SC-001 → §4 (checkpoint/resume); SC-002 → §2 (gates) + §1.3
(reconcile); SC-003 → §3 (worker write-scope); SC-004 → §6 (flag/shadow);
SC-005 → §5 (sandbox isolation). All assertions are expressible against the
DAS-1564/1565 surfaces plus the existing `apply_group` / `run_wave` /
`verify_wave_ledger` primitives.

---

## 8. Traceability matrix

| SPEC FR / SC | ADR-0035 LG | DGO-X C | This design | DAS-1567 SC |
|---|---|---|---|---|
| FR-001 — durable loop, checkpoint/resume, LangGraph as governed substrate | LG-1 | C1 | §1 (projection), §4 (checkpoint) | SC-001 |
| FR-002 — graph state is a projection/mirror of the board; divergence → board | LG-1 | C2 | §1.1–1.4 (two-hop projection, reconcile, board wins) | SC-002b |
| FR-003 — gates as interrupt/conditional-edge; no node past an open gate | LG-2 | C4 | §2 (conditional edge + `interrupt()` halt-for-Founder) | SC-002a |
| FR-004 — worker writes only ticket body/log + artifacts; no routing field | LG-3 | C3 | §3 (channel authority + graph topology) | SC-003a, SC-003b |
| FR-005 — checkpoints reconcile, no forked truth, flag-on == flag-off | LG-4 | — | §4 (subordinate checkpoint, single `run_wave` producer) | SC-001b |
| FR-006 — per-task in-tenant sandbox; no host/repo/other-task/unscoped-cred reach | LG-5 | — | §5 (contract, stub + live, four walls, escape-prevention) | SC-005a–d |
| FR-007 — `ws_c_langgraph_loop` OFF, shadow-before-drive, `/daslab-cycle` fallback | LG-5 | C5 | §6 (flag posture, shadow→enforce→drive) | SC-004a, SC-004b |
| SC-005 (design SC) — diagnostics 100/100, validators green, committed attestation | LG-4 | — | §4.2 (`run_wave` attestation, ADR-0031/0032) | covered by CI + DAS-1567 |

## 9. Open items handed downstream (not decided here)

- **DAS-1564** builds the `scripts/dgox/` LangGraph substrate adapter: the
  `project`/`reconcile` projection (§1), the gate conditional-edge + `interrupt()`
  wiring (§2), and the checkpointer-keyed-by-`run_id` reconcile through `run_wave`
  (§4) — all behind `ws_c_langgraph_loop` OFF.
- **DAS-1565** builds the `tools/sandbox/` per-task sandbox adapter: the
  `SandboxBackend` contract + the host-free `LocalStubSandbox` reference backend
  with the four fail-closed walls (§5) — buildable without a live host.
- **DAS-1566 (blocked, external dependency Q2)** wires the live `DockerSandbox`
  (E2B / OpenHands on the tenant VM) and runs the **live-host isolation smoke** —
  it needs a real Docker/E2B host, so it stays blocked; the isolation *contract*
  it satisfies is fixed here (§5).
- **DAS-1567** implements §7's negative-path spec (SC-001…SC-004 **+ SC-005**
  sandbox-escape) in `tests/test_ws_c_langgraph_loop.py`.
- **DAS-1568 (Deployment / GATE-5)** owns the runbook and keeps
  `ws_c_langgraph_loop` OFF on merge; the flip is a Founder/board act after the
  supervised first-proof gate (Q4); rollback = disabling the key.
- **Security Lead (consulted)** reviews §5 (sandbox isolation + escape-prevention +
  scoped-credential posture) against ADR-0012 and the DGO-X C-invariants;
  **CTO (accountable)** ratifies GATE-2 closure.
- The concrete module paths and the exact LangGraph checkpointer implementation
  are ADR-0035-sanctioned implementation choices left to DAS-1564/1565, not
  decided here.
