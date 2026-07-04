# ADR 0031 — The wave lifecycle mechanics move from SKILL prose into a deterministic `scripts/wave_runner.py` (`run_wave(plan, results)`) that writes a committed, hash-chained `WaveAttestation`, gated by a new `check_attestation` CI validator

- **Status:** Accepted (**GATE-1 Planning artifact — ORGANISM WS8 ATTEST, O8-T01 — 2026-07-04**)
- **Date:** 2026-07-04
- **Scope:** Platform / org-engine — the wave-runtime **execution model**. A **decision doc only**: it fixes the shape of `scripts/wave_runner.py`, the `WaveAttestation` artifact, and the `scripts/check_attestation.py` gate that the WS8 build tickets satisfy. It ships **no runner, no validator, and no dispatch-behaviour change** on merge.
- **Assignee:** chairman
- **Deciders:** **CTO (author / architecture decider)** — the wave runtime is an architecture call (RACI 3.1/3.6; the same authority that decided the load-bearing-events invariant in [ADR 0025](0025-events-load-bearing.md)). **Chairman (accountable signer)** — this ADR decides the org-engine's own **self-attestation** mechanism (the machine that proves a wave ran its declared mechanics), which is a board-oversight matter above the executive line, so the Chairman ratifies. CEO consulted — WS8 ATTEST planning owner and this ticket's author (DAS-1497 → DAS-1498). No Founder gate is triggered: this is a decision doc, not a policy / flag / model-table mutation.
- **Relates:** ORGANISM WS8 ATTEST — the closing self-audit workstream (`docs/research/ORGANISM-PROGRAM-PLAN.md` + the ATTEST-phase self-audit). Builds on and **preserves** the invariants of [ADR 0023](0023-run-model.md) (run-model: `run_id`=ULID, `board/runs/<run_id>/`, wave checkpoints, `ledger_hashes` chain), [ADR 0024](0024-span-event-schema.md) (the `span` event), and [ADR 0025](0025-events-load-bearing.md) (the event store is load-bearing; **normal-wave dispatch stays flag-on == flag-off**). Reuses — never edits — `scripts/dispatch_emitter.py` (the DAS-1455 producer), `scripts/pulse_checkpoint.py` (checkpoints / ledger chain), `scripts/guardrail_dispatch.py` (per-role tripwires), `scripts/snapshot_evidence.py` (P13 committed evidence), and the `.claude/skills/daslab-cycle/SKILL.md` step-4/5/6 prose it hardens.
- **Supersedes / Amends:** nothing in place. It **does not** edit ADR 0023/0024/0025 (append-only accepted records); it consumes their contracts. It is the WS8 counterpart of the decision-doc pattern ADR 0026–0030 established for WS2–WS7.

> **The seam this closes.** The ORGANISM ATTEST-phase self-audit named one residual
> honestly: the wave-lifecycle **event gates** (T1–T7, spans, committed-evidence,
> the `run_start`/`run_end`/`span`/checkpoint/ledger machinery) are **perma-inert in
> CI**, because the lifecycle mechanics live as **prose in `daslab-cycle/SKILL.md`
> that the orchestrator LLM is trusted to execute by hand** (steps 4, 5d–5g, 6). A
> gate that only fires when an LLM chooses to follow a paragraph cannot be *proven*
> live — CI has nothing to run and nothing committed to check. This ADR decides how
> those gates get teeth: the mechanics move out of prose into a single deterministic
> function, and each wave leaves a committed, hash-chained receipt that CI verifies.
> **No dispatch decision changes** — only where the post-decision plumbing lives.

## Context

The durable-execution core (WS1 PULSE) shipped every mechanical primitive a wave
needs — the ULID run key and `board/runs/<run_id>/` tree (ADR 0023), the typed
`run_start`/`run_end`/`span` producer (`dispatch_emitter.py`, DAS-1455), the
delta-chained tamper-evident checkpoints (`pulse_checkpoint.write_wave_checkpoint`),
the per-role guardrail tripwire (`guardrail_dispatch.py`), and the committed-evidence
snapshotter (`snapshot_evidence.write_run_evidence`, P13 / DAS-1460). ADR 0025 then
recorded that the event store is genuinely **load-bearing** as the substrate those
gates read.

But nothing **orchestrates** those primitives deterministically. The single caller
that is supposed to invoke them — in the right order, once per wave — is the
`daslab-cycle` skill, and it invokes them **as English instructions to an LLM**:

- **Step 4** tells the orchestrator to write the wave-open checkpoint
  (`pulse_checkpoint.write_wave_checkpoint(...)`).
- **Step 5d/5f/5g** tell it to emit `routing_decision`, buffer span fields, and run
  the guardrail wrapper.
- **Step 6** tells it to call `dispatch_emitter.emit_wave(records)`, then
  `snapshot_evidence.write_run_evidence(...)`, then `append_ticket_completion(...)`,
  then the wave-close `write_wave_checkpoint(...)`.

Every one of those calls is gated on the `organism_emit` feature flag and wrapped in
"failure isolation — a failed write never blocks dispatch." That is correct posture,
but it has a fatal consequence for **provability**:

1. **The gates are perma-inert in CI.** `board/.events.jsonl` and `board/runs/` are
   gitignored runtime state produced *only by a live LLM-driven wave*. On a fresh
   clone — where CI runs — there are no events, no checkpoints, no attestations. The
   event-reading gates (`check_spans`, `check_metric_gaming`, `check_ledger`,
   `check_recovery`, the T-gates) therefore read an empty store and pass **vacuously**.
   They enforce a *schema* on data that is never present when they run. The self-audit
   called this out verbatim: *"event-based gates … are perma-inert in CI — INHERENT to
   the skill-based LLM-driven runtime."*
2. **Enforcement rides on prose compliance.** Whether a wave actually emitted its
   events, ran its guardrails, and wrote its checkpoints depends entirely on the LLM
   faithfully executing ~six SKILL paragraphs. There is no committed artifact that
   proves it did, and no code path CI can run to force it. The mechanics are *shipped
   levers with no live data* (ADR 0025's own phrase for the pre-producer world), one
   level up: the producer exists, but its **caller** is prose.

The self-audit named the fix directly: *"PATH TO ≥9.5: a deterministic non-LLM
dispatcher shim that machine-attests each wave emitted events / ran guardrails / wrote
ledgers."* This ADR decides that shim — narrowed precisely so it **never** touches the
one thing ADR 0025 protects: the dispatch decision.

**AADL stage.** GATE-1 Planning for ORGANISM WS8. A decision doc; it ships no runner,
no validator, migrates nothing, and skips no gate. The build surfaces
(`scripts/wave_runner.py`, `scripts/check_attestation.py`, `metrics/attestations/`)
are named here and authored by the WS8 implementation tickets.

**Extend-vs-new posture (binding).** NEW ADR. It decides a *new* mechanism (the
wave runner + attestation), not an amendment to run-model (0023) or
events-load-bearing (0025) — those are the invariants it must preserve, cited by
reference. It **reuses** the existing producers/checkpointers/snapshotters verbatim
(`dispatch_emitter`, `pulse_checkpoint`, `guardrail_dispatch`, `snapshot_evidence`);
the runner is an *orchestrator* of them, never a re-implementation.

## Decision

**The wave LIFECYCLE MECHANICS move out of `daslab-cycle/SKILL.md` prose into a single
deterministic entry point, `scripts/wave_runner.py`, exposing one function
`run_wave(plan, results)`. The orchestrator LLM supplies the routing `plan` and the
collected `results` as DATA and makes NO mechanical decision inside the runner. The
runner is strictly POST-DECISION mechanics, gated on `organism_emit`, and it writes a
COMMITTED, hash-chained `WaveAttestation` per wave that a new `check_attestation` CI
validator verifies.**

Six parts, recorded precisely.

### 1. `run_wave(plan, results)` is the single deterministic post-decision entry point

The lifecycle plumbing that steps 4–6 describe in prose is consolidated into one pure
orchestrating function:

```python
# scripts/wave_runner.py  (build surface — WS8 implementation ticket)
def run_wave(plan: WavePlan, results: WaveResults, *, store_path=None,
             runs_dir=None, attest_dir=None, now=utcnow) -> WaveAttestation:
    """Deterministically execute the POST-DECISION mechanics of one wave.

    `plan`    — the routing DECISION, already made by the orchestrator LLM
                (which tickets, to which roles, on which models, in which wave).
    `results` — the collected per-ticket OUTCOMES (status, PR/CI/T7 evidence,
                timings), already gathered by the orchestrator LLM.

    Given (plan, results) the runner does the SAME mechanical steps every time,
    with no LLM in the loop, and returns the WaveAttestation it committed.
    """
```

- **`plan`** carries exactly what ADR 0023's `manifest.json` records: the `run_id`
  (ULID, minted by the caller via `pulse_checkpoint.generate_ulid()`), the wave index,
  the ordered ticket set, and the per-ticket `{role, model}` routing — plus the anchor
  ticket, pending interrupts, and the goal/`engine_version`. It is **the decision,
  already taken**.
- **`results`** carries exactly what `dispatch_emitter.DispatchRecord` +
  `snapshot_evidence` need: per-ticket `outcome`, `merged_pr`, `ci_status`, `t7_pass`,
  `t7_score`, start/end timestamps, span fields, and the final `{ticket_id: status}`
  map. It is **the collected reality, already observed**.
- **The function is a pure orchestration of already-shipped primitives** — it holds no
  routing logic, no selection guard, no model-tier choice. Every timestamp is
  caller-supplied (inherited from the `dispatch_emitter` / `pulse_checkpoint`
  contracts: no `utcnow()` in the pure core), so the runner is deterministic and
  unit-testable in isolation.

This replaces ~six SKILL paragraphs with **one call**. The skill's steps 4/5/6 are
reduced to: build `plan` from the (unchanged) selection/triage steps 2–3, dispatch and
collect exactly as today, then hand `(plan, results)` to `run_wave`. What the runner
does internally is no longer prose an LLM interprets — it is code.

### 2. The runner makes NO mechanical decision — flag-on == flag-off DISPATCH DECISIONS is preserved

This is the load-bearing constraint, inherited verbatim from ADR 0025 §(b):

- **The dispatch DECISION happens entirely before `run_wave` is called, and outside
  it.** Which tickets are selected, which role each goes to, and which model is passed
  (LAW 3) are decided by the orchestrator's step 2–3 triage/selection reading the
  **board ticket files** (canonical — ADR 0010 C2), never by the runner. `run_wave`
  receives that decision as the immutable `plan` argument and cannot alter it: it never
  reads the event store to route, never re-selects, never re-assigns a role or model.
- **The runner is `organism_emit`-gated, exactly like the prose it replaces.** When the
  flag is OFF, the runner is not called at all and the wave dispatches byte-identically
  (same tickets, same roles, same models, same reports). When ON, the *only* difference
  between calling and not-calling `run_wave` is the post-decision artifacts it writes
  (events in the gitignored store, files under `board/runs/`, and the committed
  attestation) — never a different dispatch. This is the ADR 0025 §(b) guarantee moved
  from prose into a function boundary: **the function's inputs are the decision; the
  function's outputs are mechanics; the two never cross.**
- **Failure isolation is preserved.** A raise inside `run_wave` is caught by the caller
  and logged in the wave report; the wave's dispatch/collect results are unaffected. A
  failed attestation write NEVER blocks dispatch. Moving the mechanics into code does
  not make them able to veto a wave — it only makes them *provable when they run*.
- **The shadow test (`tests/test_dgox_phase1_shadow.py`) still holds by property.**
  `wave_runner` READS its inputs from arguments (`plan`, `results`), not from the event
  store, and it WRITES via the existing append-only producers/checkpointers. It never
  both *reads the store* **and** *routes the normal wave* — so under the ADR 0025 §(d)
  reader-vs-router rule it is not flagged, with no filename to add to any allowlist. It
  is a write-only mechanics orchestrator, in the same category as `dispatch_emitter`
  and `pulse_checkpoint`.

### 3. What `run_wave` deterministically does — REUSE, never re-implement

Given `(plan, results)`, the runner performs, in order, exactly the calls the SKILL
prose enumerates — through the **existing** libraries, never a re-implementation:

1. **Wave-open checkpoint** — `pulse_checkpoint.write_wave_checkpoint(...)` at the
   wave-open boundary (the step-4 mechanic): board hash, event offset, delta ticket
   states, tamper-evident `ledger_hashes` chain.
2. **Guardrail tripwires** — per dispatched ticket, `guardrail_dispatch.guardrail_dispatch(...)`
   (INPUT/OUTPUT screen, bounded retry-with-feedback, escalation — the step-5g
   mechanic). The runner records each ticket's guardrail verdict; it does not re-decide
   routing.
3. **Run-lifecycle events** — `dispatch_emitter.emit_wave(records)` builds and appends
   each dispatch's `run_start` / `run_end` / `span` triplet via the DAS-1443/1455 typed
   builders (the step-5f/6 mechanic), append-only.
4. **Ticket-ledger + wave-close checkpoint** —
   `pulse_checkpoint.append_ticket_completion(...)` per finished ticket (the crash-safe
   resume ledger) and the wave-close `write_wave_checkpoint(...)` (the closing bookend).
5. **Committed evidence** — `snapshot_evidence.write_run_evidence(events, run_id, EVIDENCE_DIR)`
   using that same emitted event list (the P13 step-6 mechanic): the tracked, redacted
   `metrics/evidence/<run_id>.json`.
6. **WaveAttestation** — build and commit the receipt described in §4.

The runner imports these modules and calls their public functions; it does **not** fork
their redaction, their schemas, or their append-only discipline. It never imports
`dgox.*` for a read — it drives producers, it does not become an event reader in a
dispatch path.

### 4. The committed, hash-chained `WaveAttestation`

`run_wave` writes one **committed** attestation per wave to
`metrics/attestations/<run_id>.json` — a small, redacted, tamper-evident receipt that a
fresh-clone CI can read and check (the payload below is **illustrative** — every
value, including `engine_version`, `run_id`, timestamps, and the truncated hashes,
is a placeholder; the repo `VERSION` file is authoritative, currently `1.0.0`, and
`run_wave` stamps the live value at write time):

```json
{
  "schema": "daslab.attestation.v1",
  "run_id": "01J9Z8QK3M7Q0W9E4R5T6Y7U8I",
  "wave": 3,
  "engine_version": "1.2.0",
  "created_at": "2026-07-04T12:41:00Z",
  "tickets": ["DAS-1443", "DAS-1444"],
  "mechanics": {
    "checkpoint_open":  true,
    "guardrails_run":   true,
    "events_emitted":   { "run_start": 2, "run_end": 2, "span": 2 },
    "ledger_written":   true,
    "evidence_written": true,
    "checkpoint_close": true
  },
  "counts": { "dispatched": 2, "counted_completions": 2 },
  "ledger_hashes": { "prev": "sha256:0b7c…", "self": "sha256:9de5…" },
  "attest_chain":  { "prev": "sha256:1f3a…", "self": "sha256:7ac2…" }
}
```

Binding properties:

- **Small + redacted.** It records only structural facts about what mechanics ran —
  counts, booleans, hashes, ticket ids — never a prompt, output payload, secret, PII, or
  PR URL body (the same redaction spirit as ADR 0012 / `snapshot_evidence`: `merged_pr`
  and `t7_pass` collapse to presence-only, which the referenced `metrics/evidence`
  snapshot already enforces). It is a **receipt**, not a log.
- **COMMITTED (tracked, not gitignored).** Unlike `board/runs/` and
  `board/.events.jsonl` (runtime state, gitignored per ADR 0023 §5), the attestation
  enters git history — exactly like `metrics/evidence/` (P13). This is the whole point:
  a fresh clone, and therefore CI, can see it. The `.gitignore` **must not** cover
  `metrics/attestations/`.
- **Hash-chained two ways.** `ledger_hashes` mirrors the ADR 0023 checkpoint chain (the
  attestation binds itself to the wave's tamper-evident checkpoint ledger). `attest_chain`
  links each run's attestation to the prior run's (`prev` = SHA-256 of the previous
  attestation's canonical bytes, `self` = SHA-256 of this one with `self` excluded from
  its own preimage — the ADR 0023 §2 self-exclusion convention). A gap, a re-order, or a
  tampered receipt breaks the chain and is detectable.
- **One per wave, keyed by `run_id` (+ `wave`).** A run of N waves leaves N chained
  attestations under its `run_id`; the chain orders them by `wave`.

### 5. `check_attestation` — the CI validator that gives the receipt teeth

A new `scripts/check_attestation.py` gates CI on attestation **completeness and
integrity**, wired into the `validate` job in `.github/workflows/ci.yml` alongside
`check_metric_gaming` / `check_spans` / `check_ledger`. It mirrors the proven
`snapshot_evidence.missing_evidence_runs` → `check_metric_gaming` pattern:

- **Completeness (fail-closed, on real data).** For every run with a **counted
  completion** (the R-9 bar: merged PR + green CI + T7 pass — reusing
  `snapshot_evidence.counted_run_ids`, never re-deriving the field names), there MUST
  exist a committed `metrics/attestations/<run_id>.json` whose `mechanics` block shows
  every required mechanic ran (checkpoints, guardrails, the emitted-event counts,
  ledger, evidence). A counted run with no attestation, or an attestation with a
  mechanic marked `false`/missing, **fails CI**.
- **Integrity.** The `attest_chain` and `ledger_hashes` verify: recompute each canonical
  hash and walk the chain; a broken link fails. This is the same broken-chain principle
  `replay_qa` / `check_ledger` already apply to routing transitions and checkpoint
  ledgers.
- **Inert-by-design on an empty board.** With no counted runs (a fresh clone, a
  no-op wave), there is nothing to require and nothing to check — the gate passes
  cleanly, exactly as `check_metric_gaming` does. This is deliberate and honest: the
  gate has **teeth only when a real wave has run and committed a receipt** (see §6). It
  never fabricates a requirement, and it never scores a phantom pass as "verified."
- **Cross-check against committed evidence.** Because both the attestation and the P13
  evidence snapshot are committed and keyed by `run_id`, `check_attestation` asserts
  they agree (same counted tickets, consistent counts) — two independent committed
  artifacts that must corroborate, so a forged attestation must also forge the evidence
  snapshot to pass.

### 6. How this gives the perma-inert gates teeth — the two mechanisms

The residual the self-audit named ("gates perma-inert in CI") is closed by two
concrete, committed mechanisms — honestly, without claiming the runtime itself became
non-LLM:

- **(a) An end-to-end test drives a wave THROUGH the deterministic runner.** A WS8 test
  builds a synthetic `(plan, results)` for a small wave and calls `run_wave` against a
  `tmp_path` store/runs/attest dir, then asserts the full mechanical chain fired:
  events emitted (paired `run_start`/`run_end`, spans), checkpoints written and
  ledger-chained, guardrails invoked, evidence snapshot produced, and a valid
  `WaveAttestation` committed and chain-verifiable. Because `run_wave` is deterministic
  and clock-injected, this test runs in CI on every push — so the event/checkpoint/
  ledger/evidence machinery is now **exercised by CI**, not only by a live LLM wave.
  The gates read *real fixture data* the test produced, not an empty store.
- **(b) Committed attestations are checked in CI on live waves.** When a real wave runs
  with `organism_emit` ON, `run_wave` commits `metrics/attestations/<run_id>.json`
  alongside the wave's other tracked changes. `check_attestation` then verifies, on the
  merge, that the wave actually emitted its events / ran its guardrails / wrote its
  ledgers — reading a committed receipt, not gitignored runtime state. A wave that
  skipped its mechanics leaves either no attestation (→ CI fails the completeness check
  for its counted completions) or an attestation whose chain/evidence disagree (→ CI
  fails integrity). The gate is no longer vacuous: it has a committed artifact to bite.

Together: (a) makes the mechanics **provably exercised deterministically in CI**, and
(b) makes a **live** wave's mechanics **provably committed and checked** — the two legs
the prose-only world could not stand on.

### 7. The residual, recorded honestly

The seam is narrowed, not eliminated. The honest residual:

- **Whether the LLM actually CALLS `run_wave` remains a compliance step.** The runtime
  is still a markdown skill an orchestrator LLM executes; nothing at the language-model
  layer can *force* it to call the function, just as nothing forced it to follow the
  prose. This ADR does not claim to have made the runtime non-LLM.
- **But the trust surface shrinks from a whole prose checklist to ONE call.** Before:
  ~six independent paragraphs (checkpoint, emit, guardrail, ledger, evidence, close),
  each of which the LLM could silently skip or mis-order, with **no committed trace** of
  the omission. After: a single `run_wave(plan, results)` call whose internals are
  deterministic code — either it is called and all mechanics fire atomically as one
  unit, or it is not.
- **Done-ness flows THROUGH that one call, so non-compliance becomes DETECTABLE rather
  than silent.** A wave that omits `run_wave` produces no committed attestation for its
  counted completions, and `check_attestation` **fails CI** on the next merge. The
  omission can no longer pass unnoticed: the missing receipt is a visible, gating
  absence. The residual is therefore a *detectable* compliance gap, not a *silent* one —
  a materially smaller and honestly-bounded residual than the un-observable prose
  checklist it replaces. This is the same posture ADR 0025 took (the recovery reader is
  a narrowed, gated exception, not an abolished guarantee): the claim is precise about
  what is closed and what remains.

## Consequences

**Positive.**
- The wave mechanics become **provable**: exercised deterministically in CI via the
  end-to-end test (§6a) and verified on live waves via committed attestations (§6b). The
  event/span/checkpoint/ledger/evidence gates stop being perma-inert.
- The orchestrator's job shrinks to **decide (plan) + observe (results) + one call**;
  the error-prone middle (six prose mechanics) is code.
- Two independent committed artifacts (`metrics/evidence/` + `metrics/attestations/`)
  must corroborate per run, raising the bar for any gamed pass.
- Zero dispatch-behaviour change: flag-on == flag-off DECISIONS, preserved at a function
  boundary instead of in prose.

**Negative / accepted.**
- **The LLM-must-call-`run_wave` residual (§7) remains** — accepted, and now
  *detectable* via the missing-attestation CI failure rather than silent.
- **`check_attestation` is inert on an empty board** (no counted runs → nothing to
  require) — accepted and honest per ADR 0020 (unmeasured is SKIPPED, not false-green);
  the §6a end-to-end test is what gives the machinery teeth in the no-live-data CI case.
- **A new committed artifact class** (`metrics/attestations/`) grows with counted runs —
  accepted; receipts are small and redacted, and the class is bounded to counted
  completions (the same footprint discipline as `metrics/evidence/`).
- **A schema/field contract couples the runner, the attestation, and the validator** — a
  rename silently re-breaks the gate (the same hazard ADR 0023 §4 flagged for the
  emitter). Mitigated by a schema-conformance test required in the WS8 build ticket.

**Law check.** **Charter / RACI** — the wave runtime is an architecture call (CTO,
RACI 3.1/3.6); the org's self-attestation mechanism is board-oversight, so the Chairman
signs. **Board audit** — the board stays canonical for dispatch (ADR 0010 C2); the
runner reads its decision from `plan`, never re-routes; no silent frontmatter edits.
**AADL** — a GATE-1 Planning decision doc; no gate skipped; ships no runtime change.
**LAW 2 (no hollow gate)** — this is the ADR that gives previously-hollow event gates a
committed artifact to bite. **LAW 3 (model allocation)** — `plan` carries the explicit
per-ticket model; the runner passes it through, never infers it. **LAW 5 (green CI =
done)** — unchanged; `check_attestation` adds a committed-receipt gate on top.
**Git law / LAW 8** — unchanged (inherited from ADR 0023/0025). **Project placement** —
a platform-level ADR under `docs/`; no project artifact written.

## Enforcement / acceptance

- **This ADR is decided by the CTO** (architecture, RACI 3.1/3.6) and **ratified by the
  Chairman** (board oversight of the org's self-attestation); it is `Accepted` on merge.
- The build surfaces are **named here, authored by the WS8 implementation tickets**:
  `scripts/wave_runner.py` (`run_wave(plan, results)`), `scripts/check_attestation.py`
  (the CI gate), and the committed `metrics/attestations/<run_id>.json` receipts. This
  ticket ships the DECISION only.
- The two teeth mechanisms are the executable form of the decision: the §6a end-to-end
  test (a wave driven through `run_wave` on a `tmp_path`, asserting the full mechanical
  chain + a chain-verifiable attestation) and the §6b `check_attestation` CI gate
  (completeness + integrity + evidence cross-check, fail-closed on counted runs,
  inert-by-design on an empty board).
- This ADR is the citation any future "where do the wave lifecycle mechanics live, and
  how do we know a wave actually ran them?" question resolves to.
