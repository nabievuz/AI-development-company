# ADR 0025 — The DGO-X event store is LOAD-BEARING (producers + operator-recovery readers), superseding the Phase-1 "advisory-only shadow" framing

- **Status:** Accepted (**CTO — decider; GATE-1 Planning / RACI 3.1 A, architecture RACI 3.6 A — 2026-07-03**)
- **Date:** 2026-07-03
- **Scope:** Platform / orchestration — DGO-X event-store semantics; a **decision doc only** (no runtime dispatch change ships here)
- **Deciders:** **CTO (accountable)** — architecture/ADR authority (RACI 3.1/3.6)
- **Relates:** amends [0010](0010-adopt-dgox-graph-orchestrated-control-plane.md) §5 C3
  and [0011](0011-dgox-phase-1-data-contracts.md) §4 (the shadow-mode rule);
  builds on the run-model [0023](0023-run-model.md) and the span schema
  [0024](0024-span-event-schema.md); the events content policy
  [0012](0012-dgox-event-store-content-classification-redaction-policy.md)
- **Supersedes / Amends:** the "advisory-only shadow record" framing of **ADR-0010 §5 C3**
  and **ADR-0011 §4** — *by reference only*. ADR-0010 and ADR-0011 are **NOT edited
  in place** (append-only accepted records); this ADR records the narrowed
  invariant that replaces their absolute framing.

> This ADR canonicalizes what three ORGANISM tickets (DAS-1455, DAS-1445,
> Slice-1/ADR-0023) independently discovered while building the durable-execution
> core: `board/.events.jsonl` is now **load-bearing** — not the "advisory-only
> shadow" ADR-0011 §4 promised. It records the new invariant precisely and refines
> the shadow test (`tests/test_dgox_phase1_shadow.py`) from a per-file allowlist to
> a principled reader-vs-producer rule. **No dispatch behaviour changes on merge.**

## Context

ADR-0010 (§5 C3) and ADR-0011 (§4) fixed a Phase-1 **shadow-mode rule**: the event
store `board/.events.jsonl` is emitted and mirrored but *nothing dispatches off it*
— "the supervisor's `routing_decision` events are **advisory shadow records** —
nothing dispatches off them" (ADR-0011 §4). That framing was correct **for what
Phase-1 shipped** (a pure observer). ORGANISM then built the durable-execution core
on top of the store, and three tickets left a paper trail showing the store had
become load-bearing in ways the absolute "advisory-only" wording no longer covered:

1. **DAS-1455 — `scripts/dispatch_emitter.py` (the event PRODUCER).** Its docstring
   records that the whole observability stack (T1–T7 gates, anti-gaming R-9,
   concurrency/model-mix KPIs) **reads** `board/.events.jsonl`, and that until this
   producer existed "every event-based T-gate read 'inert'." Events are therefore
   load-bearing **as producers**: the `run_start`/`run_end`/`span` writes are what
   light up the run-model and telemetry. The emitter is **write-only** (uses
   `EventStore.append` exclusively; never reads the store to route) — a producer,
   not a dispatch-decision reader.

2. **DAS-1445 — `scripts/resume_fork.py` (the first event READER in a dispatch
   path).** Its `SHADOW-RULE CONTRACT` docstring states plainly: "This module
   READS `board/.events.jsonl` to decide which tickets to re-dispatch. This tensions
   the Phase-1 'dispatch-decision scripts don't import dgox' structural guarantee."
   It resolves the tension with three mitigations — (a) scoped **only** to the
   explicit operator-invoked `--resume`/`--fork` recovery path (normal waves
   unchanged); (b) no `dgox.*` import (it reads via `wave_kpi.read_events` +
   `replay_qa`, so the P1 import-scan is untripped); (c) failure-isolated
   (missing/corrupt store → empty set or `ValueError`, never a silent wrong
   dispatch) — and **explicitly recommends a formal ADR supersession** (docstring
   lines 41–43; DAS-1445 log). This ADR is that supersession.

3. **Slice-1 / ADR-0023 (`docs/adr/0023-run-model.md`).** The run-model adopts an
   EXTEND-not-fork posture and makes `run_start`/`run_end` the home of the metrics
   the T-gates read — implicitly relying on events being load-bearing.

Meanwhile `tests/test_dgox_phase1_shadow.py`'s P1 no-influence scan coped with the
new producers/readers by maintaining a **hand-curated per-file allowlist**
(`_EVENT_PRODUCERS = {pulse_checkpoint.py, dispatch_emitter.py, kill_drill.py}` and
`_SPAN_VALIDATORS = {check_spans.py}`). Its own inline comments call this "a
stopgap" and say a "principled refinement (flag only READERS:
`iter_events`/`read_events`) is a tracked follow-up," gated on this ADR.

**AADL stage.** GATE-1 Planning. This is an ADR (a decision doc) plus a targeted
test refinement — a Planning/design deliverable that records the invariant and
removes the stopgap; it ships **no runtime dispatch change**.

**Extend-vs-new posture (binding).** EXTEND, do not fork. ADR-0025 does **not** edit
ADR-0010 or ADR-0011 in place (they are append-only accepted records). It
**supersedes specific clauses** of them by reference and records the narrowed
invariant. The shadow test is **refined**, not rewritten — it stays green and keeps
enforcing the real intent (normal dispatch flag-on == flag-off).

## Decision

**The DGO-X event store `board/.events.jsonl` is LOAD-BEARING as a PRODUCER
substrate and as the OPERATOR-INVOKED RECOVERY reader. The Phase-1 "advisory-only
shadow record" framing of ADR-0010 §5 C3 and ADR-0011 §4 is NARROWED — not
abolished: it still holds absolutely for NORMAL `/daslab-cycle` wave dispatch, and
only there.** Three parts, recorded precisely:

### (a) Events are load-bearing as PRODUCERS and as OPERATOR-RECOVERY READERS

- **Producers are load-bearing.** `dispatch_emitter` writing `run_start`/`run_end`/
  `span` (DAS-1455) and `pulse_checkpoint` writing checkpoint/span/completion
  records (DAS-1444/DAS-1445) are load-bearing because the run-model, the T1–T7
  gates, R-9 anti-gaming, and the KPI readers all depend on those writes. A store
  with no producer is a "shipped lever with no live data" — the observability stack
  reads inert `None`. The producers are **write-only** (`EventStore.append` only;
  never read the store to route), so they are **not** dispatch-decision readers.
- **The operator-recovery path is a load-bearing READER.** `resume_fork
  --resume/--fork` (DAS-1445) reads events to reconstruct a crashed/forked run and
  decide which unfinished tickets to re-dispatch. This is a *genuine* event read in
  a dispatch path — but it exists **only** in the explicit operator-invoked recovery
  entrypoint, never in a normal wave. `kill_drill` (DAS-1451) reads events **only**
  through `resume_fork` in the operator-invoked drill path, same posture.

### (b) NORMAL wave dispatch stays flag-on == flag-off

- The `/daslab-cycle` selection/triage/routing path (steps 2–3) makes its dispatch
  decisions from the **board ticket files** (canonical — ADR-0010 C2), never from a
  shadow READ of the event store. The step-5d emission block is **post-decision,
  observational, and failure-isolated**: turning it on or off changes only the JSONL
  lines appended to the gitignored store, never which tickets are selected or which
  roles/models are assigned.
- The Phase-1 guarantee is therefore **preserved for normal waves and only
  narrowed** — it never claimed the *operator-invoked recovery* path. ADR-0011 §4's
  "nothing dispatches off them" remains true verbatim for every normal
  `/daslab-cycle` and `/daslab-run` wave; ADR-0025 clarifies that the explicit
  `--resume`/`--fork` recovery path is the one sanctioned exception, and that
  producers writing the store is not "dispatching off" it at all.

### (c) Determinism / anti-gaming is now guaranteed DIFFERENTLY

The old shadow rule protected one thing: events must not **silently steer routing**.
That protection is now provided by three stronger, committed mechanisms rather than
by keeping the store inert:

- **Committed evidence (P13 / DAS-1460).** Re-dispatch and gate decisions are scored
  against evidence committed to the repo (PR/CI/T7 records), not against a mutable,
  gitignored shadow record. An event cannot game a gate a committed artifact must
  clear.
- **The immutable T7 rubric.** Impact/quality scoring uses a fixed rubric; a route
  cannot lower its own bar by writing a favourable event.
- **Anti-gaming R-9.** A run counts as success only with a real `merged_pr` **and**
  green `ci_status` **and** `t7_pass` — the exact `metrics_lib`/ADR-0023 field
  contract. Recovery re-dispatch off events is safe because it is (i)
  operator-invoked, (ii) failure-isolated (a corrupt/broken replay chain raises,
  per the T5 zero-corrupted guardrail — it never silently re-dispatches wrong
  tickets), and (iii) gated by the same committed-evidence T-gates as any first-time
  dispatch. The append-only store (§ADR-0011 §2) plus the ADR-0023
  `ledger_hashes`/`board_hash` chain make tampering detectable.

### (d) The shadow test is refined to a principled reader-vs-producer rule

`tests/test_dgox_phase1_shadow.py`'s P1 no-influence scan is refined: the per-file
`_EVENT_PRODUCERS` / `_SPAN_VALIDATORS` allowlist is **removed** and replaced by a
principled distinction that flags a script **only** when it both

1. **READS** the event store (calls a canonical read primitive —
   `read_events` / `iter_events` / `group_runs` / `replay_run`, or opens a
   `.events.jsonl` literal in read mode — writing via `EventStore.append` /
   `build_*` is *not* a read), **and**
2. **ROUTES the normal wave** (persists a routing/status decision into a
   `board/tickets/*.md` ticket),

**unless** the reads are gated behind the explicit operator-recovery entrypoint
(`--resume`/`--fork`). Under this rule the three categories fall out by property,
with no filenames to maintain:

- **write-only producers** (`dispatch_emitter`, `pulse_checkpoint`) never call a
  read primitive ⇒ not flagged;
- **observability / gate / validation readers** (`wave_kpi`, `replay_qa`,
  `metrics_lib`, `check_spans`, `cockpit`, `trends`, the `check_*` gates, …) read
  the store but never write a normal-wave ticket routing field ⇒ they analyse, they
  do not route ⇒ not flagged;
- **operator-recovery readers** (`resume_fork`, `kill_drill`) read the store only
  under `--resume`/`--fork` ⇒ exempt by the recovery gate.

A regression that makes a *selection-path* script read events **and** route the
normal wave, outside the recovery gate, trips both conditions and is flagged. The
skill-text proof (`test_p1_skill_dispatch_decision_text_no_dgox_read`) still asserts
the `/daslab-cycle` selection text routes off no event read.

## Consequences

**Positive.** The event store's real status is recorded honestly: load-bearing as a
producer substrate and as the operator-recovery reader, advisory-only for normal
waves. The `test_dgox_phase1_shadow.py` allowlist stopgap is retired for a rule that
needs no maintenance as new producers/readers land — new producers pass by being
write-only, new observability readers pass by not routing, and any new event-driven
re-dispatch must carry the `--resume`/`--fork` recovery gate to pass. The invariant
protected by the old rule (no silent routing off events) is preserved by stronger,
committed mechanisms (P13 evidence + immutable T7 + R-9).

**Negative / accepted.** The shadow guarantee is now a **narrowed** claim rather than
an absolute one — "no event steers routing" holds for normal waves but the recovery
path *does* re-dispatch off events. Accepted: the recovery path is operator-invoked,
failure-isolated, and gated by the same committed-evidence T-gates, so it cannot
silently mis-route. The refined test flags on the read-**and**-route conjunction, so
a hypothetical normal-wave reader that only *returns* a dispatch set (without writing
a ticket) is caught by the complementary skill-text proof and by the standing
discipline that any event-driven re-dispatch must be recovery-gated, not by the
script scan alone — a smaller residual than the maintenance-heavy allowlist it
replaces.

**Law check.** **Charter / RACI** (CTO is the ADR/architecture decider — RACI
3.1/3.6; GATE-1 Planning). **Board audit** (the board stays canonical for normal
dispatch — ADR-0010 C2; no silent frontmatter edits; the append-only store
*strengthens* the audit trail). **AADL** (a decision doc closing a GATE-1 record;
no gate skipped; ships no runtime dispatch change). **LAW 2 (no hollow gate)** (the
producer makes the previously-inert T-gates read real data; re-dispatch is gated by
committed evidence, not an advisory record). **Git law / Model allocation / LAW 8**
(unchanged — inherited from ADR-0010/0011/0023). **Project placement** (a
platform-level ADR under `docs/` — ADR-0010 C6; no project artifact written).

## Enforcement / acceptance

- **This ADR is decided by the CTO** (GATE-1 Planning, RACI 3.1/3.6) and is
  `Accepted` on merge.
- The supersede relationship is expressed **only from this ADR** (this
  "Supersedes / Amends" reference to ADR-0010 §5 C3 and ADR-0011 §4). ADR-0010 and
  ADR-0011 are **not** edited in place.
- The refined `tests/test_dgox_phase1_shadow.py` reader-vs-producer rule is the
  executable form of part (d); it must stay green (P1 no-influence, P2 no-writeback,
  P3 failure-isolation) with no per-file event-producer allowlist.
- This ADR is the citation any future "are DGO-X events advisory or load-bearing?"
  question resolves to.
