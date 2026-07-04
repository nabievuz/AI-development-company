# ADR 0023 — Run-model (`run_id`/ULID, `board/runs/`, wave checkpoints, delta storage)

**Status:** Accepted
**Date:** 2026-07-03

## Context

Program **ORGANISM** WS1 "PULSE" (durable execution core) needs a first-class,
on-disk model of a **run** — one supervised execution of the org across one or
more waves — so a wave can be **interrupted and resumed without corruption**,
audited after the fact, and scored by the existing recovery/replay harness.

Today the engine has the durable pieces but not the object that binds them:

- An append-only JSONL **event store** (`board/.events.jsonl`,
  [ADR 0011](0011-dgox-phase-1-data-contracts.md)) with a common envelope
  (`event_type`, `ticket_id`, `created_at`, optional `run_id`) and two
  load-bearing shapes, `routing_decision` and `agent_invocation`. Its
  `_VALID_EVENT_TYPES` already **reserves** `run_start` / `run_end` but ships no
  typed builder or validator for them (`scripts/dgox/events.py`).
- A **replay / recovery** harness: `scripts/replay_qa.py` groups events by
  `run_id` (falling back to `ticket_id`), replays each run's `routing_decision`
  transitions in `created_at` order, and flags a **corrupted resume** on any
  broken `from_status`→`to_status` chain; `scripts/check_recovery.py` scores T5
  ("zero corrupted resumes", target ≥ 0.99) off `recovery_drill` events.
- A metrics library (`scripts/metrics_lib.py`) that already **reads a de-facto
  `run_end` schema** (`outcome`, `model`, `merged_pr`, `ci_status`, `t7_pass`,
  `t7_score`) and `recovery_drill.{outcome, corrupted}` — so any future emitter
  must match those field names exactly or the T-gates stay silently inert.

What is missing is a **run object**: no stable `run_id`, no wave-plan manifest,
no per-wave checkpoint from which a crashed run can be resumed. This ADR
**decides** that model. It is a **GATE-1 Planning** deliverable — an ADR only;
no code ships here (implementation lands in the consumer tickets
DAS-1443 / DAS-1444 / DAS-1445). Spec-of-record:
[`docs/research/ORGANISM-PROGRAM-PLAN.md`](../research/ORGANISM-PROGRAM-PLAN.md)
(§4 WS1, §9 approved defaults — Founder-approved 2026-07-03).

**Posture: EXTEND, do not fork.** The run-model layers on top of the existing
event store, reuses the reserved `run_start`/`run_end` types and the existing
`run_id` join key, and introduces **no second source of truth**. Board ticket
files remain canonical for ticket state (ADR 0010 C2); `board/.events.jsonl`
remains canonical for history (ADR 0011). `board/runs/<run_id>/` is a *new*
run-artifact tree that **references, never duplicates** those canonical stores —
it is a resumable materialized view, not a competing ledger.

## Decision

### 1. `run_id` = ULID

A run is identified by a **ULID** (Universally Unique Lexicographically Sortable
Identifier): a 128-bit value = 48-bit millisecond timestamp + 80-bit randomness,
rendered as a 26-character Crockford base32 string (e.g.
`01J9Z8QK3M7Q0W9E4R5T6Y7U8I`).

- **Why ULID over UUIDv4:** ULIDs are **lexicographically sortable in creation
  order**. Replay orders transitions by `created_at`, whose store resolution is
  one second; when several events share a second, sorting by `run_id` breaks the
  tie in true creation order, whereas a random UUIDv4 orders them arbitrarily.
- **Why ULID over a plain timestamp:** the 80 random bits make ULIDs
  **collision-safe under parallel waves** — multiple runs may start in the same
  millisecond without clashing, which a bare timestamp cannot guarantee.
- **No new dependency:** ULID is a *format*, not a library. It is generatable
  from the standard library (time + `os.urandom` + base32); the consumer ticket
  MUST NOT add a donor package for it.

`run_id` is the **single join key** across the event store, the run-artifact
tree, the ticket log, and the recovery drill — unchanged from ADR 0011.

### 2. `board/runs/<run_id>/` layout

Each run owns a directory keyed by its ULID, containing:

**`manifest.json`** — the wave **plan** (written once at run start, immutable):

```json
{
  "run_id": "01J9Z8QK3M7Q0W9E4R5T6Y7U8I",
  "engine_version": "1.0.0",
  "goal": "organism-ws1-pulse",
  "created_at": "2026-07-03T12:00:00Z",
  "waves": [
    {
      "wave": 1,
      "tickets": ["DAS-1443", "DAS-1444"],
      "routing": {
        "DAS-1443": { "role": "backend-em",    "model": "sonnet" },
        "DAS-1444": { "role": "backend-eng-1", "model": "sonnet" }
      }
    }
  ]
}
```

The manifest records the ordered **wave set**, the **ticket set per wave**, the
**per-ticket model routing** (`role` → `model`, passed explicitly per the Model
Allocation Law), and run-level metadata (`goal`, `created_at`, `engine_version`
read from `VERSION`).

**`wave-NNN.checkpoint.json`** — one per wave (`NNN` zero-padded, 1-based),
written at the wave boundary:

```json
{
  "run_id": "01J9Z8QK3M7Q0W9E4R5T6Y7U8I",
  "wave": 2,
  "created_at": "2026-07-03T12:41:00Z",
  "board_hash": "sha256:1f3a…",
  "event_offset": 10432,
  "ticket_states": { "DAS-1443": "done", "DAS-1444": "in_review" },
  "pending_interrupts": ["DAS-1445"],
  "ledger_hashes": {
    "prev": "sha256:0b7c…",
    "self": "sha256:9de5…"
  }
}
```

Fields:

- **`board_hash`** — a content hash of the board ticket set at the wave boundary,
  so a resumed run can detect that the board was mutated out-of-band since the
  checkpoint was cut.
- **`event_offset`** — the byte offset into `board/.events.jsonl` at the wave
  boundary; it marks the **resume point** (replay consumes events up to this
  offset to rebuild state, then re-dispatches only unfinished tickets).
- **`ticket_states`** — a per-ticket status snapshot stored **as a delta** (see
  §3): only the tickets whose status *changed since the previous checkpoint*.
- **`pending_interrupts`** — ticket ids halted awaiting a human interrupt answer
  (the WS1 interrupt-card mechanism, DAS-1445).
- **`ledger_hashes`** — `{prev, self}`, a hash chain linking successive
  checkpoints: `prev` = SHA-256 of the previous checkpoint's canonical bytes,
  `self` = SHA-256 of this checkpoint's canonical bytes (with `self` excluded
  from its own preimage). A gap or a tampered checkpoint breaks the chain and is
  detectable — the same broken-chain integrity principle `replay_qa.py` applies
  to routing transitions.

**`run-summary.md`** — a final, human-readable run summary (waves run, tickets
completed, outcome, KPI roll-up). This is the **only** artifact under
`board/runs/<run_id>/` that may be committed to git.

### 3. Per-step DELTA storage (not full snapshots)

Each `wave-NNN.checkpoint.json` stores only the **changes since the previous
checkpoint** — the ticket-state delta plus the advanced `event_offset` — never a
full board snapshot per wave.

- **Delta base:** the *previous* checkpoint, chained via `ledger_hashes.prev`.
  The **baseline** for wave 1 is `manifest.json` (the planned ticket set).
- **Reconstruction:** the full ticket-state at wave *N* is rebuilt by starting
  from the manifest baseline and applying the `ticket_states` deltas of
  `wave-001 … wave-NNN` in order (last-writer-wins per ticket). Equivalently,
  authoritative state is recoverable by replaying `board/.events.jsonl` up to the
  checkpoint's `event_offset` — the checkpoint is an **index/accelerator**, never
  the sole record.
- **Bloat rationale:** a full board snapshot per wave grows the run tree as
  `O(waves × board_size)`; over a long, many-wave run that is unbounded
  duplication of mostly-unchanged state. Deltas keep each checkpoint proportional
  to the *work done in that wave*, so run-tree size tracks activity, not wall
  time.

### 4. Reuse of the existing event contract (no orphan format)

The checkpoint/resume mechanism is expressed **entirely through the existing
event schema** — it introduces no parallel event format:

- Run boundaries emit the reserved **`run_start`** / **`run_end`** types
  (ADR 0011 `_VALID_EVENT_TYPES`), carrying `run_id`.
- State transitions remain **`routing_decision`** events; `replay_qa.py` groups
  them by `run_id` and replays the `from_status`→`to_status` chain **unchanged**.
- The kill/resume drill emits **`recovery_drill`** events
  (`{outcome, corrupted}`, keyed by `run_id`) that `check_recovery.py` scores for
  T5 **unchanged**.

Because `run_id` stays the join key and no field replay/recovery depends on is
renamed or dropped, **`replay_qa.py` and `check_recovery.py` continue to score
runs with zero modification**.

**Binding field-name constraint for the downstream emitter (DAS-1443 / DAS-1455).**
`scripts/metrics_lib.py` already reads a de-facto schema; the emitter that writes
these events MUST match it **exactly**, or every T-gate stays inert ("false
green"):

- `run_end` MUST carry: **`outcome`** (a value in `{success, ok, passed, done}`
  to count as success), **`model`**, **`merged_pr`**, **`ci_status`** (green ⇒
  `{green, pass, passed, success}`), **`t7_pass`**, **`t7_score`** — plus the
  envelope `event_type`, `ticket_id`, `created_at`, `run_id`.
- `recovery_drill` MUST carry: **`outcome`** (`"success"`), **`corrupted`**
  (bool), keyed by **`run_id`**.

Envelope invariants inherited from ADR 0011 / the program plan §4 hold: the store
is **append-only** (a correction is a new **compensating event**, never an
in-place rewrite), and **`created_at` is always caller-supplied** (never
generated inside a pure builder).

### 5. Approved §9 defaults encoded

Per the Founder-approved defaults in
[`ORGANISM-PROGRAM-PLAN.md`](../research/ORGANISM-PROGRAM-PLAN.md) §9 (approved
2026-07-03):

- **Checkpoint cadence:** one checkpoint per **wave boundary** (§4 WS1
  "checkpoint · resume" primitive) — not per ticket and not per event.
- **Gitignore / retention posture:** the entire `board/runs/<run_id>/` tree is
  **gitignored runtime state** (like `board/.events.jsonl` and `board/.wave-log`)
  **except** the retained, committable **`run-summary.md`**. Runtime checkpoints
  and manifests are ephemeral local artifacts; only the human-readable summary
  enters version history (§4 O1-T01 "gitignore policy, retained final summary";
  O4-T05 "final summary retained").
- **Operator-invocation contract preserved:** the run-model does **not** flip the
  standing "one operator invocation = one wave, no background timer" law — tempo
  is WS4's concern (HEARTBEAT), not the run object's.

## Consequences

**Positive**

- A crashed wave is **resumable**: replay `board/.events.jsonl` to the last
  checkpoint's `event_offset`, apply the reconstructed ticket-state, re-dispatch
  only unfinished tickets — no lost or duplicated work (verified by the WS1
  kill-drill, DAS-1444 / O1-T10).
- Runs are **auditable** and **tamper-evident** via the `ledger_hashes` chain and
  `board_hash`.
- Delta storage keeps the run tree proportional to work done, not wall-clock —
  long runs do not bloat.
- The existing replay/recovery scorers keep working **unmodified**, and the
  reserved `run_start`/`run_end` types finally have a home — lighting up the WS1
  metrics and (via the shared emitter) the WS3 telemetry seam.

**Negative / accepted**

- Delta storage trades write-simplicity for **read-time reconstruction**: rebuild
  requires walking the checkpoint chain (or replaying events). Accepted — the
  chain is short (one link per wave) and the event log is the always-available
  fallback.
- The `board_hash` / `ledger_hashes` integrity checks add a small hashing cost at
  each wave boundary. Accepted — it is the price of tamper-evidence.
- The emitter (DAS-1443) inherits a **hard field-name contract** (§4); a rename
  silently re-breaks the gates. Mitigated by a schema-conformance test required
  in that ticket.

**Implementation notes for consumers (not shipped here)**

- Add a `.gitignore` rule covering `board/runs/` while **un-ignoring** the
  summary, e.g.:

  ```gitignore
  # ORGANISM run-artifact tree (runtime state — ADR 0023); keep only the summary
  board/runs/
  !board/runs/*/run-summary.md
  ```

- Register typed `run_start` / `run_end` builders + validators in
  `scripts/dgox/events.py` (DAS-1443 / O1-T02), matching §4 field names exactly.
