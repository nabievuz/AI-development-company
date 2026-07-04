# ADR 0032 — Attestation becomes HARNESS-FORCED: `run_wave` co-produces a committed, append-only, hash-chained `board/wave-ledger.jsonl` entry atomically with each attestation, and a new `check_wave_reconciliation` validator enforces a committed bijection + per-run wave-chain continuity + board terminality (baseline-grandfathered)

- **Status:** Accepted (**GATE-1 Planning artifact — ORGANISM WS9 HARNESS, harness-forced attestation — 2026-07-04**)
- **Date:** 2026-07-04
- **Scope:** Platform / org-engine — the wave-runtime **attestation regime**. A **decision doc only**: it fixes the shape of the committed `board/wave-ledger.jsonl` entry `run_wave` co-produces, the `scripts/check_wave_reconciliation.py` reconciliation validator, and the committed `board/.attestation-baseline` grandfather anchor that the HARNESS-phase build tickets satisfy. It ships **no ledger writer, no validator, no baseline file, and no dispatch-behaviour change** on merge.
- **Assignee:** chairman
- **Deciders:** **CTO (author / architecture decider)** — the wave-runtime attestation regime is an architecture call (RACI 3.1/3.6; the same authority that decided the wave runner + attestation in [ADR 0031](0031-wave-runner-attestation.md) and the load-bearing-events invariant in [ADR 0025](0025-events-load-bearing.md)). **Chairman (accountable signer)** — this ADR strengthens the org-engine's own **self-attestation** mechanism (the machine that proves a wave that committed done-ness left durable, reconciled, tamper-evident proof), a board-oversight matter above the executive line, so the Chairman ratifies — exactly as for ADR 0031. CEO consulted — WS9 HARNESS planning owner and this ticket's author (DAS-1503 → DAS-1504). No Founder gate is triggered: this is a decision doc, not a policy / flag / model-table mutation.
- **Relates:** ORGANISM WS9 HARNESS — the audit-closure final phase (`docs/research/ORGANISM-PROGRAM-PLAN.md` + the ATTEST re-audit residual). **Extends — does not replace** [ADR 0031](0031-wave-runner-attestation.md): 0031 stays the attestation *base* (the deterministic `run_wave` and the committed `metrics/attestations/<run_id>.json` receipt verified by `scripts/check_attestation.py`); 0032 adds a **second committed record** — the hash-chained wave-ledger — and the reconciliation validator that binds the two records to each other and to the board. Preserves the invariants of [ADR 0023](0023-run-model.md) (run-model: `run_id`=ULID, checkpoint `ledger_hashes` chain, self-exclusion hashing), [ADR 0024](0024-span-event-schema.md), and [ADR 0025](0025-events-load-bearing.md) (**normal-wave dispatch stays flag-on == flag-off**). Reuses — never edits — `scripts/wave_runner.py`, `scripts/check_attestation.py`, `scripts/snapshot_evidence.py`, and the `.claude/skills/daslab-cycle/SKILL.md` step-6 `run_wave` call.
- **Supersedes / Amends:** nothing in place. It **does not** edit ADR 0031 (an append-only accepted record); it consumes 0031's `WaveAttestation` contract and adds a co-committed ledger + a cross-record validator on top. It is the WS9 counterpart of the decision-doc pattern ADR 0026–0031 established for WS2–WS8.

> **The seam this closes.** ADR 0031 shrank wave-mechanics enforcement from a
> six-paragraph prose checklist to **one call** and gave the previously-perma-inert
> event gates teeth — but it recorded its residual with total honesty (0031 §7): *whether
> the LLM actually **calls** `run_wave` is still a compliance step.* The ATTEST re-audit
> named the irreducible-at-that-layer shape of that gap precisely: a **total silent
> omission** — an LLM-driven wave that commits its work (moves tickets to `done`, lands
> PRs) but never calls `run_wave` — leaves **no committed attestation and no committed
> trace of the omission**, because `check_attestation` is inert on an empty store and
> there is **no committed "a wave happened here ⇒ an attestation MUST exist" cross-check**.
> ADR 0032 installs exactly that cross-check. It makes attestation **harness-forced** for
> any wave that commits *any* work: a second committed, append-only, hash-chained record
> (`board/wave-ledger.jsonl`) is co-produced atomically with each attestation, and a
> reconciliation validator binds the committed ledger, the committed attestations, and the
> board's post-baseline `done` transitions into one mutually-corroborating triangle that CI
> checks. **No dispatch decision changes** — only what a committed wave is forced to leave
> behind, and what CI is forced to reject when that proof is missing, skipped, or tampered.

## Context

[ADR 0031](0031-wave-runner-attestation.md) shipped the deterministic
`scripts/wave_runner.py:run_wave(plan, results)`: the wave lifecycle mechanics (open/close
checkpoints, `run_start`/`run_end`/`span` emission, guardrail tripwires, ledgers,
committed redacted evidence, and a committed doubly hash-chained
`WaveAttestation` at `metrics/attestations/<run_id>.json`) moved out of `daslab-cycle`
SKILL prose into one call, and `scripts/check_attestation.py` gates that receipt's
**completeness + integrity** fail-closed in CI + diagnostics. `daslab-cycle/SKILL.md`
step 6 collapsed the whole lifecycle to a single `run_wave` call whose output is committed.

That regime is genuinely strong **once `run_wave` is called** — a partial, forged, or
tampered attestation is caught with teeth (self-hash recompute, chain walk, cross-check
against the committed evidence snapshot). But it has one structural gap, which 0031 §7
and the ATTEST re-audit both stated plainly:

1. **`check_attestation` is inert on an empty store (ADR 0020 — honest, by design).** With
   no committed attestations, the gate exits 0 — a fresh clone has nothing to check. This
   is correct (unmeasured is SKIPPED, never false-green), but it means the *absence* of an
   attestation is, by itself, never a failure.
2. **There is no committed record of "a wave happened."** `board/.events.jsonl` and
   `board/runs/` are gitignored runtime state (ADR 0023 §5); they do not exist on a fresh
   clone / in CI. The only committed proof a wave ran is the attestation itself and its
   sibling evidence snapshot — both of which a skipped `run_wave` simply never writes.
3. **Therefore a total silent omission leaves no trace.** An LLM-driven wave can commit its
   *actual work* — edit ticket frontmatter to `done`, land PRs, merge branches — and never
   call `run_wave`. No attestation is committed, no evidence is committed, and because
   `check_attestation` has nothing to bite on for a run that produced no receipt, **CI stays
   green**. The board records done-ness; nothing committed records that the wave which
   produced it ran (or skipped) its declared mechanics. The omission is *silent*.

The re-audit named the fix directly (recorded in ArcRift, `daslab`): the residual is
*"closable ONLY by making `run_wave` HARNESS-FORCED — a done-transition ↔ attestation
reconciliation so a wave that committed done-ness cannot do so without a durable reconciled
receipt."* This ADR decides that reconciliation. The forcing does **not** come from
compelling the LLM to call a function (nothing at the language-model layer can) — it comes
from making a committed wave's *work product* (a `done` transition on the board) and its
*proof* (the attestation) into two committed artifacts a CI validator **requires to agree**,
anchored by a committed baseline so the requirement is fail-closed on new work yet green on
the existing repo.

**Why a second committed record (the ledger), not just the attestation.** The attestation
alone cannot self-report its own absence. A committed, append-only, **hash-chained** ledger
solves three things the single per-run attestation file cannot:

- **An omission becomes a chain break, not a silent gap.** The ledger is one append-only
  file with a running `prev_hash`/`self_hash` chain across *all* waves of *all* runs. A
  recorded-but-skipped wave (a gap in a run's `wave` sequence) and a deleted/edited line
  (a broken hash link) are both **committed, detectable** states — where a missing
  standalone `<run_id>.json` was merely an absence.
- **It is the committed index the bijection checks against.** The ledger enumerates which
  attestations *must* exist; the attestation store is checked to *be* exactly that set. A
  forger must now forge **both** committed records *and* keep two independent hash chains
  consistent (the ledger's, and each attestation's own `attest_chain` from ADR 0031 §4).
- **It is small enough to always co-commit.** One JSONL line per wave — ids, paths, and
  hashes only — so co-committing it atomically with the attestation is cheap and never a
  reason to skip the mechanic.

**AADL stage.** GATE-1 Planning for ORGANISM WS9. A decision doc; it ships no ledger
writer, no validator, no baseline file, migrates nothing, and skips no gate. The build
surfaces (the `run_wave` ledger co-write, `scripts/check_wave_reconciliation.py`,
`board/wave-ledger.jsonl`, `board/.attestation-baseline`) are named here and authored by
the WS9 implementation tickets.

**Extend-vs-new posture (binding).** This **EXTENDS** the ADR 0031 attestation regime; it
does not replace it. 0031 stays the base (the `run_wave` mechanics + the committed
`WaveAttestation` + `check_attestation`'s completeness/integrity gate). 0032 adds the
committed hash-chained ledger co-produced by the same `run_wave` call, the
`check_wave_reconciliation` cross-record validator, and the committed baseline. It
**reuses** the shipped `run_wave` / attestation / evidence contracts verbatim; the new
validator only *reads and cross-checks* committed artifacts — it never re-derives a schema
or re-implements a mechanic.

## Decision

**Attestation becomes HARNESS-FORCED. `run_wave` ATOMICALLY co-produces, with each
committed `WaveAttestation`, a COMMITTED, append-only, hash-chained entry in a TRACKED
`board/wave-ledger.jsonl` (NOT the gitignored `board/.wave-log`). A new
`scripts/check_wave_reconciliation.py` validator enforces, in CI + diagnostics, a BIJECTION
between committed ledger entries and committed attestations, per-run wave-sequence CHAIN
continuity, and board TERMINALITY + COVERAGE anchored by a committed `board/.attestation-baseline`
that grandfathers pre-regime `done` tickets. Going forward, a wave that commits done-ness
through `run_wave` cannot do so without a durable, reconciled attestation + ledger — so
omission or tampering of any RECORDED wave, and any post-baseline `done` transition not
covered by a committed ledger entry, is CI-detectable.**

Four parts, recorded precisely.

### 1. `run_wave` co-produces a committed, append-only, hash-chained `board/wave-ledger.jsonl` entry, atomically with each attestation

The same deterministic `run_wave(plan, results)` call from ADR 0031 — which already writes
the committed `metrics/attestations/<run_id>.json` receipt — additionally appends **one
line** to a **TRACKED** `board/wave-ledger.jsonl` for that wave, in the same load-bearing
step that writes the attestation (§6 of the ADR 0031 mechanic sequence). The two writes are
**one atomic unit**: either both the attestation file and its ledger line are produced (and
committed together with the wave's other tracked changes), or `run_wave` raises and the wave
is recorded as a logged, CI-detectable failure — never one without the other.

Each ledger entry has exactly this shape (the payload below is **illustrative** — every
value, including the truncated hashes and timestamps, is a placeholder):

```json
{
  "run_id": "01J9Z8QK3M7Q0W9E4R5T6Y7U8I",
  "wave": 3,
  "ticket_ids": ["DAS-1443", "DAS-1444"],
  "attestation_path": "metrics/attestations/01J9Z8QK3M7Q0W9E4R5T6Y7U8I.json",
  "attestation_hash": "sha256:9de5…",
  "prev_hash": "sha256:1f3a…",
  "self_hash": "sha256:7ac2…",
  "created_at": "2026-07-04T12:41:00Z"
}
```

Binding properties of the ledger entry and file:

- **The exact field set is `{run_id, wave, ticket_ids, attestation_path, attestation_hash, prev_hash, self_hash, created_at}`** — no more, no less. `ticket_ids` is the wave's dispatched/terminal ticket set (sorted, matching the attestation's `tickets`); `attestation_path` is the repo-relative path of the co-produced attestation; `attestation_hash` is the SHA-256 of that committed attestation's canonical bytes (binding the ledger line to the exact receipt — a swapped attestation changes this hash).
- **TRACKED, append-only, one line per wave.** `board/wave-ledger.jsonl` enters git history — it is **not** the gitignored `board/.wave-log` (a human-readable KPI scratch file) and **not** the gitignored `board/.events.jsonl` runtime store. The WS9 build ticket must ensure `.gitignore` does **not** cover `board/wave-ledger.jsonl` (the `board/.wave-log` / `board/.events.jsonl` ignore lines already present must not be widened to catch it). Lines are only ever appended; an existing line is never rewritten.
- **Hash-chained (`prev_hash` → `self_hash`), independent of the attestation's own `attest_chain`.** This is the ledger's *own* running chain across every appended line, in append order: `prev_hash` = the `self_hash` of the immediately preceding ledger line (or the genesis sentinel `sha256:0×64` for the first line), and `self_hash` = SHA-256 of the line with `self_hash` excluded from its own preimage (the ADR 0023 §2 self-exclusion convention `wave_runner` already uses for `attest_chain`). This is a **second, independent** committed chain layered on top of each attestation's internal `attest_chain` — a deletion or edit of any ledger line breaks this chain and is detectable, and a forged wave must keep *both* chains consistent.
- **Deterministic and caller-clocked.** Like the rest of `run_wave`, the ledger co-write reads no clock and makes no routing decision: `created_at` is the caller-supplied wave timestamp, `run_id`/`wave`/`ticket_ids` come from the immutable `plan`, and `attestation_path`/`attestation_hash` come from the receipt `run_wave` just wrote. Given `(plan, results)` the ledger line is a pure function of them plus the current chain tip. This keeps the WS9 end-to-end test able to drive the co-write on fixture data.

### 2. `check_wave_reconciliation` — the validator that binds the two committed records to each other and to the board

A new `scripts/check_wave_reconciliation.py`, wired into the `validate` job in
`.github/workflows/ci.yml` alongside `check_attestation` and into `diagnostics.py`, enforces
three properties over the committed ledger, the committed attestations, and the board. It
**reuses** `wave_runner`'s hashing/schema constants and `snapshot_evidence`'s helpers; it
only reads and cross-checks.

- **(a) Bijection — committed ledger ⇄ committed attestations.** Every committed
  `board/wave-ledger.jsonl` entry MUST have its committed `metrics/attestations/<run_id>.json`
  attestation, and vice versa — **no orphan in either direction**. For each matched pair the
  validator asserts the **ticket set agrees** (`ledger.ticket_ids == attestation.tickets`)
  and the **`attestation_hash` agrees** (recompute the SHA-256 of the committed attestation's
  canonical bytes and require it equals `ledger.attestation_hash`). A ledger line with no
  attestation, an attestation with no ledger line, a ticket-set mismatch, or a hash mismatch
  each **fails CI**. (Where a run legitimately carries multiple waves under one `run_id`, the
  pair key is `(run_id, wave)`, matched against the attestation's `wave` field; the ADR 0031
  runtime's "one invocation = one wave = one run" model makes this the common `run_id`-keyed
  case.)
- **(b) Per-run wave-sequence CHAIN continuity.** Two chain checks. First, the ledger's own
  `prev_hash`/`self_hash` chain MUST verify end-to-end in append order (each `self_hash`
  recomputes over the self-excluded preimage; each `prev_hash` links to genesis or the prior
  line's `self_hash`) — a broken link means a line was deleted, reordered, or tampered.
  Second, **per `run_id`, the `wave` indices MUST be gap-free and contiguous** (`1..K` with
  no missing index): a recorded wave 1 and wave 3 with no wave 2 is a **recorded-but-skipped
  wave** and **fails**. A gap is the committed fingerprint of a wave that was skipped
  mid-sequence — precisely the mid-run omission that the empty-store `check_attestation`
  could not see.
- **(c) Board TERMINALITY + COVERAGE, anchored by the committed baseline.** Two directions.
  **Terminality (ledger → board):** every ticket named in any committed ledger entry MUST be
  **terminal (`done`)** on the board — an attested-as-complete ticket that is not actually
  `done` is an inconsistency and fails. **Coverage (board → ledger):** every board ticket that
  became terminal **after** the `board/.attestation-baseline` (§3) MUST be covered by some
  committed ledger entry's `ticket_ids` — a post-baseline `done` ticket with **no** covering
  ledger entry means a wave committed done-ness without co-producing its ledger + attestation,
  and **fails**. Coverage is the **harness-forcing arm**: it is what makes a committed
  done-transition *require* a committed, reconciled receipt. Pre-baseline `done` tickets are
  grandfathered (§3) and never trigger coverage.

Fail-closed on real data, inert-by-design on none (ADR 0020, mirroring `check_attestation`):
with **no committed ledger entries and no post-baseline `done` tickets** there is nothing to
require and nothing to check — the gate exits 0 cleanly (a fresh clone before the regime has
any recorded work), never a fabricated pass. The gate **BITES** the moment either a committed
ledger entry exists (bijection + chain) or a post-baseline `done` transition appears (coverage).

### 3. The committed `board/.attestation-baseline` grandfathers pre-regime `done` tickets

A committed `board/.attestation-baseline` pins the repository HEAD SHA at the instant the
regime goes live (the WS9 build ticket writes it once, at regime start, and commits it). Its
sole job is to make the coverage arm (§2c) **fail-closed on new work yet green on the existing
repo**: a board ticket is **grandfathered** — exempt from the coverage requirement — if it was
already terminal as of the baseline SHA (i.e. its `done` transition predates the regime and
therefore predates any ledger). Only tickets that become `done` **after** the baseline are held
to "must have a committed ledger entry."

- **Why it is required.** Without it, turning on the coverage check would instantly fail CI on
  every one of the repo's already-`done` tickets (62/62 board-done at regime start, ADRs
  0023–0031, none of which has a wave-ledger entry). The baseline is the honest cut-line
  between "the world before harness-forced attestation" (grandfathered) and "the world after"
  (forced), so the regime can be adopted on a live repo without a false red.
- **A single committed anchor, not a per-ticket exemption list.** The baseline is one HEAD SHA;
  the validator derives "was this ticket terminal at the baseline?" from git history against
  that SHA (or from a committed, baseline-stamped snapshot the build ticket may materialise if
  git archaeology per-run proves too costly — an implementation detail for WS9, constrained
  here to: the anchor is committed, singular, and set once at regime start). It is **not**
  editable to launder a later omission: moving the baseline forward would be a
  governance-relevant, reviewed change to a committed file, not a silent per-wave escape hatch.

### 4. The forward guarantee — and the honest residual

Going forward, with the regime live: a production wave that commits done-ness **through
`run_wave`** cannot do so without co-producing a durable, reconciled attestation **and** ledger
line — because `run_wave` writes both atomically, and `check_wave_reconciliation` requires every
post-baseline `done` ticket to be covered by a committed ledger entry that bijects to a committed
attestation with a matching hash and lies on an unbroken, gap-free chain. Concretely, this makes
**three** previously-silent failure modes CI-detectable:

- **Omission of a recorded wave's proof** — a committed ledger line whose attestation is missing
  or whose hash/ticket-set disagrees fails the bijection (§2a).
- **A mid-sequence skip** — a gap in a run's `wave` indices, or a broken ledger hash-link from a
  dropped line, fails chain continuity (§2b).
- **Committing done-ness without any proof at all** — a post-baseline `done` ticket with no
  covering ledger entry fails coverage (§2c). This is the case ADR 0031's empty-store
  `check_attestation` could not see.

**The residual, recorded with total honesty (MANDATORY).** This regime forces attestation for
any wave that does **any committed work** — because "committed work" that matters (a `done`
transition on the board) is exactly what the coverage arm keys on, and the hash-chained ledger
makes omission and tampering of any *recorded* wave break a committed chain. But it does **not**
reach zero, and this ADR does not claim it does:

- **The irreducible floor is a wave that commits absolutely nothing.** A wave that moves no
  ticket to `done`, lands no PR, and commits nothing to the repo produces no post-baseline
  terminal transition for coverage to require, no ledger line, and no attestation — and there is
  nothing committed to reconcile against. But such a wave **also delivered nothing**: it changed
  no committed state, so there is no committed work whose proof could be missing. The floor is
  therefore not a leak of *undelivered-but-hidden* work — it is the empty case, where "no proof"
  and "no product" coincide.
- **An LLM-driven runtime cannot be forced below that floor without removing the LLM.** Nothing
  at the language-model layer can compel the model to call `run_wave`; the runtime is still a
  markdown skill an orchestrator LLM executes. What the harness *can* force — and now does — is
  that the model cannot **commit done-ness** without also committing the reconciled proof, on
  pain of a red CI. It cannot force the model to do work it declines to do, nor to attest a wave
  in which it committed nothing.
- **What actually moved.** The residual moves from **"silent omission leaves no trace"**
  (ADR 0031 §7: a skipped `run_wave` on a real, work-committing wave passed CI unnoticed) to
  **"omission breaks a committed chain"** (a work-committing wave that skips `run_wave` now fails
  coverage; a tampered or mid-sequence-skipped recorded wave breaks a committed hash-chain). It
  moves the residual **toward** — **not to** — zero. The precise, honestly-bounded claim: the
  only wave an LLM-driven runtime can still run without a detectable trace is one that commits
  nothing and therefore delivers nothing.

## Consequences

**Positive.**
- **Attestation is harness-forced for work-committing waves.** A committed `done` transition
  after the baseline *requires* a committed, reconciled attestation + ledger line; skipping the
  proof fails CI (coverage). The dominant real-world omission mode — a wave that did work but
  skipped its receipt — moves from silent to detectable.
- **Omission and tampering of any recorded wave break a committed chain.** The append-only,
  hash-chained ledger turns a dropped line, a reordered line, or a mid-sequence wave skip into a
  committed, CI-detectable break — where ADR 0031's per-run attestation store could only see a
  receipt that was written.
- **Three committed artifacts must now corroborate per counted wave** (`metrics/evidence/` +
  `metrics/attestations/` + `board/wave-ledger.jsonl`, cross-checked against the board), raising
  the bar for a gamed pass: a forger must forge all three and keep two independent hash chains
  consistent.
- **The existing repo stays green.** The committed baseline grandfathers all pre-regime `done`
  tickets, so the regime is adoptable on the live 62/62-done board without a false red.
- **Zero dispatch-behaviour change.** flag-on == flag-off DECISIONS (ADR 0025) — the ledger
  co-write is one more post-decision artifact inside the existing `organism_emit`-gated
  `run_wave`; when the flag is OFF, `run_wave` is a no-op and no ledger line is written, exactly
  as today.

**Negative / accepted.**
- **The commits-nothing floor remains (Decision §4)** — accepted and stated plainly: a wave that
  commits nothing delivered nothing, and an LLM-driven runtime cannot be forced below that
  without removing the LLM. This is a *smaller and honestly-bounded* residual than ADR 0031's
  ("silent omission on a real wave"), not its elimination.
- **`check_wave_reconciliation` is inert on an empty regime** (no committed ledger entries and no
  post-baseline `done` tickets → nothing to require) — accepted and honest per ADR 0020
  (unmeasured is SKIPPED, not false-green); the WS9 end-to-end test is what exercises the
  co-write + reconciliation on fixture data so the machinery has teeth even in the no-live-data
  CI case.
- **A new committed artifact (`board/wave-ledger.jsonl`) grows one line per wave** — accepted;
  lines are tiny (ids, one path, three hashes, a timestamp), append-only, and bounded to
  work-committing waves. A `.gitignore` mistake that ignores it would silently defeat the regime
  — mitigated by an explicit build-ticket assertion that the file is tracked and by the
  end-to-end test committing a sample line.
- **A schema/field contract now couples `run_wave`, the attestation, the ledger line, and two
  validators** — a rename silently re-breaks reconciliation (the same hazard ADR 0023 §4 /
  ADR 0031 flagged). Mitigated by reusing `wave_runner`'s constants as the single SSOT and by a
  schema-conformance test required in the WS9 build ticket.
- **Baseline governance.** Moving `board/.attestation-baseline` forward could grandfather away a
  later omission — accepted and bounded: it is a committed file, so any move is a reviewed,
  governance-relevant diff, never a silent per-wave escape hatch.

**Law check.** **Charter / RACI** — the wave-runtime attestation regime is an architecture call
(CTO, RACI 3.1/3.6); the org's self-attestation mechanism is board-oversight, so the Chairman
signs. **Board audit** — the board stays canonical for dispatch (ADR 0010 C2); the validator
*reads* the board's `done` transitions to reconcile, it never routes or edits frontmatter.
**AADL** — a GATE-1 Planning decision doc; no gate skipped; ships no runtime change. **LAW 2 (no
hollow gate)** — this ADR gives the empty-store attestation gate a committed "a wave happened ⇒
proof must exist" cross-check, so a skipped-proof wave is no longer a vacuous pass. **LAW 3
(model allocation)** — unchanged; `plan` still carries the explicit per-ticket model into the
attestation, the ledger records only ids/paths/hashes. **LAW 5 (green CI = done)** — strengthened:
`check_wave_reconciliation` adds a committed-reconciliation gate on top of green CI. **Git law /
LAW 8** — unchanged (inherited from ADR 0023/0025/0031). **Project placement** — a platform-level
ADR under `docs/`; the ledger + baseline live under `board/` (org-engine state), no project
artifact written; `board/tickets/` carries no `project:` field.

## Enforcement / acceptance

- **This ADR is decided by the CTO** (architecture, RACI 3.1/3.6) and **ratified by the Chairman**
  (board oversight of the org's self-attestation); it is `Accepted` on merge.
- The build surfaces are **named here, authored by the WS9 implementation tickets**: the
  `run_wave` ledger co-write to `board/wave-ledger.jsonl` (the exact eight-field entry, atomic
  with the attestation), `scripts/check_wave_reconciliation.py` (the bijection + chain-continuity
  + terminality/coverage gate wired into `ci.yml` + `diagnostics.py`), and the committed
  `board/.attestation-baseline` grandfather anchor. This ticket ships the DECISION only — no
  ledger writer, no validator, no baseline file, no `.gitignore` edit.
- The teeth are the executable form of the decision: a WS9 end-to-end test drives a synthetic
  wave through `run_wave` on a `tmp_path` and asserts the co-produced ledger line + attestation
  reconcile (bijection, chain, coverage) and that a deleted line / a mid-sequence gap / an
  uncovered post-baseline `done` ticket each fail `check_wave_reconciliation`; plus the CI gate on
  live waves' committed ledger + attestations.
- This ADR is the citation any future "how do we know a wave that committed done-ness actually
  left a durable, reconciled, tamper-evident receipt — and what is the exact floor below which we
  cannot force an LLM-driven runtime?" question resolves to.

## Amendment — 2026-07-04 (HFIX hardening; append-only, implementation-truth)

> An adversarial break-it probe of the shipped regime found **two real gaps between this
> decision doc and the code that implemented it**. This amendment records the fixes and
> corrects one overclaim in §2c/§3 so the ADR matches what the harness actually does. It is a
> factual reconciliation of doc-to-code, not a new architectural decision; **CTO (author) /
> Chairman (signer) should ratify** it as they did the base ADR.

1. **The COVERAGE arm was VACUOUS — now it is live.** §2c requires every post-baseline,
   `run_id`-bearing terminal board ticket to be covered by a committed ledger entry — but
   *nothing wrote the `run_id` marker onto tickets*, so the arm had **zero subjects** and could
   never bite. Fix: `run_wave` now **stamps `run_id: <run_id>` into the YAML frontmatter of each
   planned ticket** as it processes the wave (an idempotent, post-decision, `organism_emit`-gated,
   per-ticket failure-isolated write — a missing ticket file is logged, never crashes the wave; a
   flag-off wave stamps nothing, so flag-on == flag-off dispatch decisions still hold). An
   attested-wave `done` ticket now carries the marker the coverage arm keys on, giving it real
   subjects and turning a **forged `run_id`** (one with no covering, reconciling ledger entry)
   into a CI failure.

2. **The baseline was DECORATIVE — now it is load-bearing; §3's "derives … from git history"
   is corrected.** §2c/§3 claimed the validator "derives 'was this ticket terminal at the
   baseline?' from git history." The shipped `read_baseline` did **not**: it only checked the SHA
   was hex and ≥7 chars, discarded the value, and never consulted git — so a **forged or advanced
   baseline** would silently grandfather post-regime dones. **No per-ticket git-history terminality
   derivation was ever implemented, and this amendment does not add one.** What is now implemented
   and true: `read_baseline` **verifies the baseline SHA is a real commit that is an ancestor of
   HEAD** (`git cat-file -e` + `git merge-base --is-ancestor`); a non-existent or non-ancestor
   (advanced) baseline **fails the gate**, in a non-git checkout the ancestry check is skipped with
   a logged note (ADR 0020 — unmeasured is skipped, never a crash). The grandfather cut-line stays
   a single committed anchor (§3), now provably genuine rather than an unverified token. The §2c/§3
   phrase "derives … from git history" should be read as this **ancestry verification of the anchor
   commit**, not a per-ticket historical-terminality query.

**What this does and does NOT close (honest residual, extending §4).** These fixes make the
coverage arm *live for attested-wave dones* and kill the decorative baseline — a wave that calls
`run_wave` now cannot commit a `done` ticket (stamped with a `run_id`) without a covering,
reconciling, ancestor-anchored receipt. They do **NOT** move the irreducible floor of §4: an agent
that **skips `run_wave` entirely** also never stamps a `run_id`, so its `done` tickets look
identical to pre-regime grandfathered ones and escape the coverage arm. That total-omission floor
is unchanged and remains, per §4, only forceable below by removing the LLM. The precise post-HFIX
claim: *for any wave that goes through `run_wave`, omission or forgery of its proof is
CI-detectable and its grandfather anchor is git-verified; a wave that bypasses `run_wave` wholesale
remains the irreducible floor.*

**Chairman ratification — 2026-07-04.** Ratified. Verified the amendment against the shipped code (`scripts/wave_runner.py` step 1b `_stamp_wave_run_ids` — `organism_emit`-gated, idempotent, per-ticket failure-isolated; `scripts/check_wave_reconciliation.py` `read_baseline`/`_baseline_ancestry_error` — `git cat-file -e` + `merge-base --is-ancestor`, fail-closed on a forged/advanced anchor, skip-with-note in non-git): both fixes are HONEST implementation-truth, the §2c/§3 "derives … from git history" overclaim is correctly narrowed to anchor-ancestry verification, and the total-omission floor of §4 is not claimed closed. Gates green at ratification (diagnostics 100/100, pytest 0 failed). — Chairman of the Board.
