---
id: DAS-1442
title: Author ADR-0023 run-model (run_id/ULID, board/runs, wave-checkpoints, delta storage)
status: done
assignee: chairman
author: ceo
dept: engineering
priority: p1
parent: DAS-1440
goal: organism-ws1-pulse
zone: docs/adr
created: 2026-07-03
updated: 2026-07-03
---

## Description

**What & why.** The ORGANISM program (WS1 "Pulse") needs a first-class,
durable model of a **run** — one supervised execution of the org across one or
more waves — so that a wave can be interrupted and resumed without corruption,
audited after the fact, and scored by the existing recovery/replay harness.
Today the engine has an append-only event store (`board/.events.jsonl`,
[ADR 0011](../../docs/adr/0011-dgox-phase-1-data-contracts.md)) and a
replay/recovery harness, but there is **no on-disk run object** that ties a run
together: no stable `run_id`, no wave plan manifest, no per-wave checkpoint from
which a crashed run can be resumed. This ticket authors the ADR that **decides**
that model. It is a GATE-1 Planning deliverable — an ADR only; no code ships
here (implementation lands in the consumer tickets DAS-1443/1444/1445).

**Embedded context (so no archaeology is needed):**

- **Event store & envelope** — `scripts/dgox/events.py` defines the append-only
  JSONL store and the common envelope `event_type`, `ticket_id`, `created_at`,
  and an **optional `run_id`** (validated non-empty-string-when-present by
  `validate_envelope`). Two load-bearing shapes exist: `routing_decision`
  (Shape A) and `agent_invocation` (Shape B, where `run_id` is **required**).
  `_VALID_EVENT_TYPES` already reserves `run_start` / `run_end` for future
  phases. The ADR must reuse this envelope and these reserved types — it must
  **not** invent a parallel event format.
- **Replay / recovery scoring** — `scripts/replay_qa.py` groups events by
  `run_id` (falling back to `ticket_id`), replays each run's `routing_decision`
  transitions in `created_at` order, and flags a **corrupted resume** on any
  broken `from_status`→`to_status` chain. It optionally emits `recovery_drill`
  events consumed by `scripts/check_recovery.py` (T5, "zero corrupted resumes"
  guardrail). The run-model decided here MUST keep these two scripts scoring
  **unchanged** — i.e. the checkpoint/resume mechanism must still surface as the
  same `routing_decision` + `recovery_drill` event contract, so `run_id` remains
  the join key and no field replay depends on is renamed or dropped.
- **ADR conventions** — per `docs/adr/README.md`, ADRs are append-only, take the
  next free number (0022 is the last, so this is **0023**), and each records
  Context / Decision / Consequences. `docs/adr/0022-semantic-versioning-policy.md`
  is the format-of-record template to mirror (title `# ADR 0023 — …`,
  `**Status:**`, `**Date:**`, then `## Context`, `## Decision`, `## Consequences`).

**Extend-vs-new posture: EXTEND, do not fork.** The run-model is layered on top
of the existing event store and reuses the reserved `run_start`/`run_end` event
types and the existing `run_id` join key. `board/runs/<run_id>/` is a **new**
directory (a run-artifact tree), but it references — never duplicates — the
canonical `board/.events.jsonl`. No new event schema, no second source of
truth for ticket state (the board files remain canonical per ADR 0010 C2).

**Key existing files this ADR touches or references (paths):**

- `docs/adr/0023-run-model.md` — **new**, the deliverable.
- `docs/adr/README.md` — add the index row + theme sentence.
- `docs/adr/0011-dgox-phase-1-data-contracts.md` — the event-store contract this
  ADR extends (reserved `run_start`/`run_end`, envelope, `run_id`).
- `scripts/dgox/events.py` — the envelope + shapes the ADR must stay compatible
  with (reference in the Decision/Consequences as the binding contract).
- `scripts/replay_qa.py` and `scripts/check_recovery.py` — the scorers that must
  keep working unchanged (reference as the compatibility constraint).
- `docs/research/ORGANISM-PROGRAM-PLAN.md` — spec-of-record (§9 approved
  defaults must be encoded where the ADR touches them).

**AADL stage:** GATE-1 Planning.

**Decisions the ADR must record:**

1. **`run_id` = ULID.** Lexicographically sortable, timestamp-prefixed,
   collision-resistant; sorts in creation order (helpful for `created_at`-tie
   ordering in replay). State why ULID over UUIDv4 (sortable) and over a plain
   timestamp (collision-safe under parallel waves).
2. **`board/runs/<run_id>/` layout:**
   - `manifest.json` — the wave **plan**: the ordered wave set, the ticket set
     per wave, and the model routing decision per ticket (role → model), plus
     run-level metadata (goal, created_at, engine version).
   - `wave-NNN.checkpoint.json` — one per wave, capturing: `board_hash`
     (content hash of the board ticket set at wave boundary), `event_offset`
     (byte or line offset into `board/.events.jsonl` marking the resume point),
     `ticket_states` (per-ticket status snapshot **as a delta** — see below),
     `pending_interrupts`, and `ledger_hashes` (hash chain linking successive
     checkpoints so tampering/gaps are detectable).
   - Everything under `board/runs/<run_id>/` is **gitignored runtime state**
     (like `board/.events.jsonl`) **except** a final human-readable run
     **summary** that may be committed.
3. **PER-STEP DELTA storage (not full snapshots).** Each `wave-NNN.checkpoint`
   stores only the *changes* since the previous checkpoint (ticket-state deltas
   + event_offset advance), never a full board snapshot per wave, to prevent
   checkpoint bloat across long runs. The ADR must state the delta base
   (previous checkpoint, chained via `ledger_hashes`) and how a full state is
   reconstructed (replay deltas from run start / from `manifest.json` baseline).
4. **Reuse of the existing event contract.** The checkpoint/resume mechanism is
   expressed through the existing `routing_decision` + `recovery_drill` events
   (and the reserved `run_start`/`run_end` types) so `replay_qa.py` and
   `check_recovery.py` score a run **unchanged** — `run_id` stays the join key;
   no orphan format is introduced.
5. **Encode approved §9 defaults** from `docs/research/ORGANISM-PROGRAM-PLAN.md`
   wherever the run-model touches them (e.g. checkpoint cadence, retention,
   gitignore posture) — cite §9 explicitly.

Also add the ADR **index row** (`| 0023 | Run-model — … | Accepted | 2026-07-03 |`)
and extend the relevant **theme** paragraph in `docs/adr/README.md`.

## Acceptance criteria

- [ ] `docs/adr/0023-run-model.md` authored and merged, following the
      0022 format (`# ADR 0023 — …`, `**Status:**`, `**Date:**`,
      `## Context` / `## Decision` / `## Consequences`).
- [ ] `docs/adr/README.md` index row added for 0023 and the theme paragraph
      updated to mention the run-model.
- [ ] Decision specifies `run_id = ULID` with the rationale (sortable +
      collision-safe vs. UUIDv4 / plain timestamp).
- [ ] Run / checkpoint / manifest shapes are specified **with concrete field
      names**: `manifest.json` (wave plan + per-wave ticket set + per-ticket
      model routing + run metadata); `wave-NNN.checkpoint.json` (`board_hash`,
      `event_offset`, `ticket_states`, `pending_interrupts`, `ledger_hashes`).
- [ ] The **per-step delta-storage** decision is explicit — deltas not full
      snapshots, delta base + reconstruction path stated, bloat rationale given.
- [ ] The `board/runs/<run_id>/` tree is declared gitignored runtime state
      **except** the final committed run summary.
- [ ] The ADR **reuses the existing event schema** (`routing_decision` +
      `recovery_drill` + reserved `run_start`/`run_end` from
      `scripts/dgox/events.py`) with `run_id` as the join key — no orphan
      format — and explicitly states that `replay_qa.py` / `check_recovery.py`
      continue to score runs unchanged.
- [ ] Approved §9 defaults from `docs/research/ORGANISM-PROGRAM-PLAN.md` are
      encoded/cited where the run-model touches them.

**Produces:** `adr-0023` (consumed by DAS-1443 / DAS-1444 / DAS-1445).

## Log

### 2026-07-03 — CEO

Created from ORGANISM program-plan decomposition (/daslab-plan). Spec-of-record: docs/research/ORGANISM-PROGRAM-PLAN.md.

### 2026-07-03 — CTO

Authored `docs/adr/0023-run-model.md` (GATE-1 Planning artifact of ORGANISM WS1 PULSE),
mirroring the 0022 format (`# ADR 0023 — …`, `**Status:**`/`**Date:**`, Context/Decision/
Consequences). The ADR decides:

1. **`run_id` = ULID** — 48-bit ms timestamp + 80-bit randomness, 26-char Crockford base32;
   chosen over UUIDv4 (ULID is lexicographically sortable → breaks `created_at` second-
   resolution ties in true creation order) and over a plain timestamp (random bits are
   collision-safe under parallel waves). No new dependency — ULID is a format, stdlib-generatable.
2. **`board/runs/<run_id>/` layout** with concrete field names: `manifest.json` (immutable
   wave plan = ordered wave set + per-wave ticket set + per-ticket `role`→`model` routing +
   `goal`/`created_at`/`engine_version`); `wave-NNN.checkpoint.json` (`board_hash`,
   `event_offset` into `board/.events.jsonl` = resume point, `ticket_states` (delta),
   `pending_interrupts`, `ledger_hashes` `{prev,self}` chain); `run-summary.md` = the one
   committable artifact.
3. **Per-step DELTA storage** — each checkpoint stores only ticket-state changes since the
   previous checkpoint (base = prior checkpoint via `ledger_hashes.prev`; baseline =
   manifest); full state reconstructed by applying deltas in order or replaying events to
   `event_offset`. Bloat rationale stated (avoids O(waves × board_size) duplication).
4. **Reuse of the existing event contract** — checkpoint/resume rides `routing_decision` +
   `recovery_drill` + reserved `run_start`/`run_end`, `run_id` stays the join key, no orphan
   format → `replay_qa.py`/`check_recovery.py` score unchanged. Encoded the **binding
   field-name constraint** the downstream emitter (DAS-1443/1455) inherits: `run_end.{outcome,
   model,merged_pr,ci_status,t7_pass,t7_score}` and `recovery_drill.{outcome,corrupted}` must
   match `metrics_lib.py` exactly or the T-gates stay inert; append-only (compensating events),
   `created_at` caller-supplied.
5. **§9 approved defaults** (Founder-approved 2026-07-03) cited: checkpoint cadence = one per
   wave boundary; `board/runs/` gitignored except the retained `run-summary.md`; operator-
   invocation contract preserved (no background timer — tempo is WS4).

Added the `0023` index row + a new "Durable execution — ORGANISM WS1 PULSE" theme paragraph to
`docs/adr/README.md`. No code shipped (ADR-only Planning deliverable); the `.gitignore` rule
and typed `run_start`/`run_end` builders are noted as consumer-ticket work (DAS-1443/1444/1445).

Verified: `diagnostics.py` and `board_lint.py` (results in report). Git discipline: local-only
this wave (no push / no PR) per Founder's pending ORGANISM remote decision.

Set `status: in_review`. Reviewer routing: my (CTO) manager per ROUTING.md is CEO, but
CEO is this ticket's author — ROUTING.md's rule "if the manager IS the author, escalate one
level" routes review up to CEO's manager, **Chairman of the Board**. `assignee: chairman`.

### 2026-07-03 — Chairman of the Board

**GATE-1 (Planning) sign-off — PASS.** Reviewed `docs/adr/0023-run-model.md` in full against
this ticket's 8 acceptance criteria and the AADL §3 Stage-1 checklist. Reviewer routing
confirmed legitimate: ROUTING.md's "manager-is-author → escalate one level" correctly lands
CTO→CEO(author)→Chairman, so this is not a self-review.

Verified (cross-checked against the actual code, not just the ADR prose):

1. **`run_id` = ULID with rationale** — §1 states sortable-vs-UUIDv4 (breaks `created_at`
   second-resolution ties in true creation order) and collision-safe-vs-plain-timestamp
   (80 random bits under parallel waves), plus "no new dependency — ULID is a format,
   stdlib-generatable." AC-3 satisfied.
2. **Concrete field names** — §2 gives `manifest.json` (ordered `waves` → per-wave `tickets`
   → per-ticket `routing` role→model + `goal`/`created_at`/`engine_version`) and
   `wave-NNN.checkpoint.json` (`board_hash`, `event_offset`, `ticket_states`,
   `pending_interrupts`, `ledger_hashes {prev,self}`). AC-4 satisfied.
3. **Per-step DELTA storage explicit** — §3 states delta base = prior checkpoint via
   `ledger_hashes.prev` (baseline = manifest), reconstruction = apply deltas in order OR
   replay events to `event_offset`, and the O(waves × board_size) bloat rationale. AC-5.
4. **Gitignored-except-summary** — §2/§5 + the implementation-note `.gitignore` stanza
   (`board/runs/` ignored, `!board/runs/*/run-summary.md` un-ignored). AC-6.
5. **No orphan format; reuses existing contract** — §4 rides `routing_decision` +
   `recovery_drill` + reserved `run_start`/`run_end`, `run_id` stays the join key.
   Confirmed against `scripts/dgox/events.py`: `_VALID_EVENT_TYPES` reserves
   `run_start`/`run_end`; envelope `run_id` is optional-non-empty-when-present. AC-7.
6. **Emitter bound to `metrics_lib`'s EXACT field names** — checked
   `scripts/metrics_lib.py` directly: `run_end` is read for `outcome`, `model`, `merged_pr`,
   `ci_status`, `t7_pass`, `t7_score`; `recovery_drill` for `outcome=="success"` + `corrupted`,
   keyed by `run_id`. ADR §4's binding constraint matches the reader **byte-for-byte** — a
   rename would leave the T-gates silently inert, and the ADR calls that out + requires a
   schema-conformance test in DAS-1443. This is the highest-risk item and it is correct.
7. **§9 approved defaults cited** — §5 cites Founder-approved (2026-07-03) cadence
   (one/​wave boundary, §4 WS1), gitignore/retention (O1-T01 / O4-T05), and the preserved
   operator-invocation contract (§9 item 3, "NOT a daemon"). AC-8.
8. **Format + README** — mirrors 0022 (`# ADR 0023 —`, `**Status:**`/`**Date:**`,
   Context/Decision/Consequences); README.md carries the 0023 index row + a new "Durable
   execution — ORGANISM WS1 PULSE" theme paragraph. AC-1/AC-2.

**GATE-1 checklist mapping.** This ADR is ONE Planning artifact within WS1, not the whole
program gate. It fully satisfies the two checklist items in its remit — **scope boundaries
explicit** (ADR-only, EXTEND-not-fork, consumer tickets named) and **data/technical
feasibility confirmed** (rides the existing event store, no new deps, stated reconstruction
path). The remaining GATE-1 items — measurable business KPI baseline, finance-analyst token/
infra budget, legal-analyst risk-ethics sign-off — are **deferred to sibling program-plan
Planning artifacts owned by senior-pm / finance-analyst / legal-analyst**; they are out of
scope for this engine-internal ADR and are NOT a reason to block it (AADL §0: engine tooling
carries the methodology without the customer-agent-specific artifacts).

Decision: all acceptance criteria met, all load-bearing claims verified against code — I do
not return a deficient Planning artifact. `status: done`. Note: under the Founder's local-only
directive, "done" here = green local validators (diagnostics/board_lint per the CTO log) + this
GATE-1 review — no PR / no CI (the ADR is committed to local main). Consumer tickets
DAS-1443 / DAS-1444 / DAS-1445 may now proceed on `adr-0023`; DAS-1443 inherits the hard
field-name contract + the required schema-conformance test.
