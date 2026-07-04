---
id: DAS-1504
title: Author ADR-0032 harness-forced attestation and reconciliation
status: done
assignee: chairman
author: ceo
dept: engineering
priority: p1
parent: DAS-1503
goal: organism-ws9-harness
zone: docs/adr
created: 2026-07-04
updated: 2026-07-04
---

## Description

**What:** Author `docs/adr/0032-harness-forced-attestation.md` — an
architecture decision that forces wave attestation to be *durable, reconciled,
and tamper-evident* at the harness level, closing the residual gap left after
ADR-0031 (wave-runner attestation) and the ATTEST re-audit.

**Why:** ADR-0031 introduced wave attestation, but the re-audit surfaced a
residual: attestation as it stands can be **omitted or tampered with** without
CI detecting it, because there is no committed, cross-checkable record binding
each wave to its attestation. A wave that marks tickets done through `run_wave`
must not be able to do so without leaving a durable, reconciled proof — and any
mid-sequence skip or tampering of a *recorded* wave must be CI-detectable. This
is GATE-1 Planning work: it decides the design, it does not implement it.

**Embedded context (ORGANISM HARNESS phase):** This ticket comes from the
ORGANISM HARNESS-phase decomposition (audit-closure final phase). The
spec-of-record is `docs/research/ORGANISM-PROGRAM-PLAN.md` plus the ATTEST
re-audit residual. This is the org-engine (DasLab platform) — there is **no
`project:` field** and no project name in any engine file.

**Extend-vs-new:** This *extends* the ADR-0031 attestation regime rather than
replacing it — 0031 stays the attestation base; 0032 adds the committed,
hash-chained ledger and the reconciliation validator on top. New artifacts
introduced by the decision: a tracked `board/wave-ledger.jsonl`, a new
`scripts/check_wave_reconciliation.py` validator, and a committed
`board/.attestation-baseline`. The ADR document itself is new (0032).

**Key files + paths (READ before authoring):**
- `docs/adr/README.md` — ADR index; add the 0032 row + theme (highest is
  currently 0031 → author 0032).
- `docs/adr/0031-wave-runner-attestation.md` — the base regime being extended.
- `scripts/wave_runner.py` — where `run_wave` co-produces the ledger entry.
- `scripts/check_attestation.py` — the existing attestation validator that the
  new reconciliation validator complements.
- `.claude/skills/daslab-cycle/SKILL.md` — the wave-dispatch skill whose
  behavior the regime constrains.
- New (decided, not implemented here): `docs/adr/0032-harness-forced-attestation.md`,
  `board/wave-ledger.jsonl` (TRACKED, append-only, hash-chained — NOT the
  gitignored `.wave-log`), `scripts/check_wave_reconciliation.py`,
  `board/.attestation-baseline`.

**The decision to record (four parts):**

1. **Co-produced committed ledger.** `run_wave` atomically co-produces, with
   each attestation, a **committed, append-only, hash-chained** entry in
   `board/wave-ledger.jsonl` (TRACKED — not the gitignored `.wave-log`). Each
   entry has the shape:
   `{run_id, wave, ticket_ids, attestation_path, attestation_hash, prev_hash, self_hash, created_at}`.

2. **`check_wave_reconciliation` validator.** A new validator enforces, in CI +
   diagnostics:
   - **Bijection** between committed wave-ledger entries and committed
     attestations — each ledger entry has its attestation with a matching ticket
     set + hash; each attestation has its ledger entry.
   - **Wave-sequence chain continuity per run** — a gap (a recorded-but-skipped
     wave) is a FAIL.
   - **Terminality** — attested tickets are terminal (done) on the board.

3. **Committed baseline grandfather.** A committed `board/.attestation-baseline`
   pins the HEAD SHA at regime start, grandfathering pre-regime done tickets so
   the existing repo stays green.

4. **Forward guarantee.** Going forward, a production wave that marks done-ness
   through `run_wave` cannot do so without a durable, reconciled
   attestation + ledger, making omission or tampering of any *recorded* wave
   detectable.

**Residual recorded honestly (MANDATORY in the ADR):** This regime forces
attestation for any wave that does *any committed work*, and makes mid-sequence
skips and tampering CI-detectable. The **irreducible floor** is a wave that
**commits nothing at all** — which also delivered nothing. An LLM-driven runtime
cannot be forced below that floor without removing the LLM. State this plainly;
do not overclaim total coverage.

Set this ticket's `assignee: chairman` when reassigning per the theme owner.

## Acceptance criteria

- [ ] `docs/adr/0032-harness-forced-attestation.md` authored + README row added
      (theme: highest ADR 0031 → author 0032).
- [ ] Committed, hash-chained `board/wave-ledger.jsonl` entry co-produced by
      `run_wave` (with the exact field set) is decided.
- [ ] `check_wave_reconciliation` validator decided — bijection +
      chain-continuity + terminality — plus its CI/diagnostics wiring.
- [ ] Committed `board/.attestation-baseline` grandfathers existing done tickets.
- [ ] The exact irreducible floor (a wave that commits nothing) recorded
      honestly in the ADR.
- [ ] diagnostics 100/100.
- [ ] org-engine constraints held: NO `project:` field; no other file created.

## Log

### 2026-07-04 — CTO
Authored `docs/adr/0032-harness-forced-attestation.md` (GATE-1 Planning decision
doc; ships no code) and added the README index row + WS9 HARNESS theme (highest
prior ADR 0031 → author 0032). Recalled ArcRift `daslab` first: it confirmed the
0031 residual the re-audit named — *"closable ONLY by making run_wave
HARNESS-FORCED (non-LLM wrapper + done-transition↔attestation reconciliation)"*
with the irreducible residual being a total silent omission (LLM never calls
run_wave; check_attestation inert on an empty store, no committed
'wave-happened ⇒ attestation-must-exist' cross-check). ADR-0032 installs exactly
that cross-check.

THE DECISION (four parts, recorded precisely in the ADR):
1. `run_wave` ATOMICALLY co-produces, with each committed `WaveAttestation`, one
   line in a TRACKED, append-only, hash-chained `board/wave-ledger.jsonl` (NOT the
   gitignored `board/.wave-log`) — exact eight-field entry `{run_id, wave,
   ticket_ids, attestation_path, attestation_hash, prev_hash, self_hash,
   created_at}`; `prev_hash`/`self_hash` are a SECOND committed chain (ADR-0023 §2
   self-exclusion hashing) independent of the attestation's own `attest_chain`.
2. `scripts/check_wave_reconciliation.py` (CI + diagnostics) enforces: (a)
   bijection committed ledger ⇄ committed attestations (matching ticket set +
   `attestation_hash`, no orphan either way); (b) per-run wave-sequence chain
   continuity (ledger hash-chain verifies AND each run's `wave` indices gap-free —
   a recorded-but-skipped wave FAILS); (c) board terminality (attested tickets are
   `done`) + coverage (every post-baseline `done` ticket covered by a committed
   ledger entry — the harness-forcing arm). Fail-closed on real data, inert on an
   empty regime (ADR-0020).
3. Committed `board/.attestation-baseline` (HEAD SHA at regime start) grandfathers
   pre-regime `done` tickets so the existing 62/62-done repo stays green.
4. Forward guarantee: a wave that commits done-ness through `run_wave` cannot do so
   without a durable reconciled attestation + ledger; omission/tampering of any
   RECORDED wave and any uncovered post-baseline `done` transition is CI-detectable.

RESIDUAL (honest, mandatory in the ADR): HARNESS-forces attestation for any wave
that commits ANY work; makes mid-sequence skips + tampering CI-detectable via a
durable broken hash-chain. IRREDUCIBLE FLOOR = a wave that commits absolutely
nothing (which also delivered nothing) — an LLM-driven runtime cannot be forced
below that floor without removing the LLM. Moves the residual from "silent omission
leaves no trace" to "omission breaks a committed chain" — TOWARD, not TO, zero.

EXTENDS ADR-0031 (does not replace it): 0031 stays the attestation base; 0032 adds
the committed hash-chained ledger + reconciliation validator + baseline on top.
Reuses — never edits — wave_runner.py / check_attestation.py / snapshot_evidence.py
/ ADR 0023–0025 / 0031. Org-engine constraints held: NO `project:` field; only the
ADR + README touched (no ledger writer, validator, baseline file, or `.gitignore`
edit created — those are the WS9 build tickets' surfaces).

VERIFY (green): pytest 0 failed, diagnostics 100/100, board_lint 0. Committed to
local branch `feat/das-1504-adr-0032-harness` (LOCAL ONLY — no push/PR).
Set `status: in_review`, `assignee: chairman` (author is ceo). Routing to Chairman
for ratification (this ADR decides the org-engine's own self-attestation
mechanism — board oversight above the executive line, per ADR-0031's precedent).

### 2026-07-04 — Chairman of the Board
GATE-1 sign-off / ratification of ADR-0032 (harness-forced attestation +
reconciliation). Reviewed `docs/adr/0032-harness-forced-attestation.md` and the
`docs/adr/README.md` index row against the ticket acceptance criteria + the
GATE-1 Planning gate. VERDICT: **PASS — ADR ratified, Accepted.**

Verified point by point:
1. **Committed, tracked, hash-chained ledger, atomic with each attestation.**
   §1 fixes `run_wave` to atomically co-produce, per attestation, one line in a
   TRACKED `board/wave-ledger.jsonl` (explicitly NOT the gitignored
   `board/.wave-log`/`.events.jsonl`; build ticket must keep `.gitignore` off
   it), append-only, exact eight-field set `{run_id, wave, ticket_ids,
   attestation_path, attestation_hash, prev_hash, self_hash, created_at}`. The
   `prev_hash`/`self_hash` chain is stated (§1, line 146) as a SECOND, INDEPENDENT
   committed chain layered on top of each attestation's own `attest_chain`
   (self-exclusion hashing, ADR 0023 §2) — the requested independence is explicit.
   "Both or `run_wave` raises" atomicity recorded (lines 122–124).
2. **check_wave_reconciliation enforces the required triangle.** §2: (a) bijection
   committed ledger ⇄ committed attestations (matching ticket set + recomputed
   `attestation_hash`, no orphan either way); (b) per-run wave-sequence chain
   continuity — ledger hash-chain verifies end-to-end AND `wave` indices gap-free
   per run, a recorded-but-skipped wave FAILS; (c) board terminality + coverage,
   grandfathered by the committed `board/.attestation-baseline` (§3, single
   committed HEAD-SHA anchor set once at regime start, not a per-ticket exemption
   list, not silently editable). Fail-closed on real data, inert-by-design on an
   empty regime (ADR 0020) — consistent with `check_attestation`.
3. **ATTEST residual closed at the right seam.** The coverage arm (§2c, the
   "harness-forcing arm") is exactly what catches a wave that commits done-ness
   but never calls `run_wave` — a post-baseline `done` ticket with no covering
   ledger entry FAILS. Mid-sequence skip / tamper of a RECORDED wave breaks a
   committed hash-chain or a gap-free `wave` sequence (§2b, §4). The three
   previously-silent modes are enumerated (§4, lines 224–232).
4. **The honest floor is stated plainly, not overclaimed.** §4 (lines 234–259)
   records the irreducible floor as a wave that commits absolutely nothing — which
   also delivered nothing ("no proof" and "no product" coincide; it is the empty
   case, not hidden undelivered work), and that an LLM-driven runtime cannot be
   forced below it without removing the LLM. The ADR explicitly says it "does not
   reach zero, and this ADR does not claim it does" and moves the residual
   "toward — not to — zero" (title, README row, §Decision, §4, §Consequences all
   agree). NO overclaim of total coverage.
5. **Numbering + index.** Correctly numbered 0032 (highest prior 0031 → next free
   0032); README row present (line 40) and every cross-link (0031, 0023–0025,
   0010, 0020) resolves; WS9 HARNESS theme paragraph added. Minor cosmetic note
   (non-blocking, not a GATE-1 defect): the README table row for 0032 sits just
   above 0031 rather than strictly after — both are 2026-07-04 WS8/WS9 siblings;
   left as-is.
6. **Decision-doc-only + org-engine constraints held.** Confirmed on disk that
   `board/wave-ledger.jsonl`, `board/.attestation-baseline`, and
   `scripts/check_wave_reconciliation.py` do NOT yet exist — the ADR ships the
   decision only; those are the WS9 build surfaces. No `project:` field (board_lint
   R9 green). Reuses — never edits — `wave_runner.py` / `check_attestation.py` /
   `snapshot_evidence.py` / ADR 0023–0025 / 0031; Law check (§Consequences) sound
   (LAW 2 no-hollow-gate, LAW 5 green-CI, board stays canonical for dispatch).

GATES (green): `diagnostics.py` = 100/100; `board_lint.py` = 0 violations (67
tickets); `pytest -q` = 1686 passed, 1 skipped, 0 failed. ADR is committed to
local `main` (c0f0566). LOCAL-ONLY: no push, no PR, no remote contact.

Governance authority: ratifying the org-engine's own self-attestation mechanism
is board oversight above the executive line, per the ADR-0031 precedent — within
Chairman charter, no Founder gate triggered (decision doc, not a policy/flag/
model-table mutation). Set `status: done`.

### 2026-07-04 — CEO
Created from ORGANISM HARNESS-phase decomposition (/daslab-plan, audit-closure
final phase). Spec-of-record: docs/research/ORGANISM-PROGRAM-PLAN.md + the ATTEST
re-audit residual.
READ: docs/adr/README.md, docs/adr/0031-wave-runner-attestation.md,
scripts/wave_runner.py, scripts/check_attestation.py,
.claude/skills/daslab-cycle/SKILL.md.
Scope+acceptance (expand; keep frontmatter exact): GATE-1 Planning. Author
docs/adr/0032-harness-forced-attestation.md deciding: (1) run_wave co-produces a
COMMITTED, append-only, hash-chained wave-ledger entry (board/wave-ledger.jsonl,
TRACKED — NOT the gitignored .wave-log) atomically with each attestation —
{run_id, wave, ticket_ids, attestation_path, attestation_hash, prev_hash,
self_hash, created_at}; (2) a new check_wave_reconciliation validator enforces,
in CI + diagnostics: a BIJECTION between committed wave-ledger entries and
committed attestations (each ledger entry has its attestation with matching
ticket set + hash; each attestation has its ledger entry), wave-sequence CHAIN
continuity per run (a gap = a recorded-but-skipped wave = FAIL), and attested
tickets are terminal on the board; (3) a committed board/.attestation-baseline
(HEAD SHA at regime start) grandfathers pre-regime done tickets so the existing
repo stays green; (4) going forward a production wave that marks done-ness
through run_wave cannot do so without a durable reconciled attestation+ledger,
making omission/tampering of any recorded wave detectable. RECORD THE RESIDUAL
HONESTLY: this forces attestation for waves that do ANY committed work + makes
mid-sequence skips and tampering CI-detectable; the irreducible floor is a wave
that commits nothing at all (which also delivered nothing) — an LLM-driven
runtime cannot be forced below that without removing the LLM. README row + theme
(highest ADR 0031 -> author 0032). Set ticket assignee: chairman.
