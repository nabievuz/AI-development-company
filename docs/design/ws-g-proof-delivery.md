# WS-G PROOF design — golden-eval delivery scorecard, the 0→100 evidence + attestation gate, the proof-project skeleton, and the immutable scope-lock

- **Status:** Design (AADL Stage 2 — GATE-2) — awaiting review (CTO accountable; Security Lead consulted — attestation integrity; CPO consulted — this fixes the completion contract's measurable surface)
- **Date:** 2026-07-24
- **Ticket:** DAS-1590 (WS-G Design); epic DAS-1588 (MUSTAQIL WS-G PROOF)
- **Author:** Backend EM (responsible); CTO (accountable stage owner); Security Lead (consulted — attestation hash-chain integrity)
- **Binds to:** [ADR-0037](../adr/0037-end-to-end-autonomous-delivery-target.md) (ED-1…ED-5 — the MUSTAQIL completion contract, **Accepted** 2026-07-24), [`docs/specs/007-mustaqil-ws-g-proof/SPEC.md`](../specs/007-mustaqil-ws-g-proof/SPEC.md) (FR-001…FR-008, SC-001…SC-005, reviewed), [ADR-0020](../adr/0020-gate-promotion-no-false-green.md) (no false-green — unmeasured is SKIPPED, never green), [ADR-0031](../adr/0031-wave-runner-attestation.md)/[ADR-0032](../adr/0032-harness-forced-attestation.md) (the committed, hash-chained `WaveAttestation` + `check_attestation` gate), [ADR-0014](../adr/0014-native-clarify-gate.md) (the Clarify gate), [ADR-0029](../adr/0029-guild-model.md) (extend-vs-new: the golden-eval substrate is EXTENDED, never forked), the landed golden-eval harness (`scripts/agent_eval.py`, `evals/`, `evals/e2e/`), the wave runner + committed receipts (`scripts/wave_runner.py`, `scripts/check_attestation.py`, `metrics/attestations/`, `metrics/evidence/`), `scripts/snapshot_evidence.py` (`counted_run_ids` — the R-9 counted-completion bar), `scripts/diagnostics.py` (the 100/100 release gate), the PROJECT-OS pack + gateway compiler (`scripts/gateway_compile.py`, `evals/e2e/sample-pack`), `governance/policies/ai-agent-lifecycle.md` §2 (the canonical project skeleton), `config/features.yaml` (`ws_g_proof`, DEFAULT OFF — DAS-1543), Founder discovery answers Q1 (proof = the WS-H control-plane dashboard slice) and Q7 (shipped = merged + green CI + deployed to the tenant VM)
- **Downstream:** DAS-1591 (Development — the delivery scorecard + SWE-bench-style golden harness, extending `agent_eval.py`/`evals/`), DAS-1592 (Development — the evidence + attestation gate `scripts/check_evidence_gate.py` chaining onto ADR-0031/0032), DAS-1593 (Development — the proof-project skeleton bootstrap under `projects/<proof-name>/` + its own board), DAS-1594 (Testing — the negative-path suite this doc hands it §6), DAS-1595 (Deployment — deploy the proof to the tenant VM; genuinely infra-gated, carried `blocked` absent a VM), DAS-1596 (Maintenance — scorecard-health / drift eval)

> **Scope of this doc.** WHAT the WS-G *org-engine* machinery is — the rails that
> *measure and prove* an autonomous delivery — and HOW its pieces interlock: the
> golden-eval delivery **scorecard** (+ anti-gaming probe), the 0→100 **evidence +
> attestation gate**, the **proof-project skeleton** bootstrap, and the **immutable
> scope-lock** — each traced to its FR and to an ADR-0037 ED invariant, plus the
> negative-path spec the Testing ticket (DAS-1594) implements. It ships **no runtime
> code**: the scorecard extension, the evidence-gate validator, the skeleton
> bootstrap, and the scope-lock check are built by DAS-1591/1592/1593 against this
> design. This design is about the **PROOF's rails, NOT the proof project itself** —
> the proof project (the WS-H dashboard slice) is bootstrapped later by DAS-1593 and
> lives entirely under `projects/<proof-name>/` (Project Placement Law). The landed
> golden-eval harness (`scripts/agent_eval.py`, `evals/`), the wave runner + committed
> receipts (`scripts/wave_runner.py`, `scripts/check_attestation.py`,
> `metrics/attestations/`, `metrics/evidence/`), `scripts/snapshot_evidence.py`,
> `scripts/diagnostics.py`, and the PROJECT-OS pack machinery
> (`scripts/gateway_compile.py`) are the reference this design **reuses** — cited, not
> modified here (this ticket touches only `docs/design/` + the ticket file).
> Everything is behind `ws_g_proof` (`config/features.yaml`, from DAS-1543) DEFAULT
> **OFF**.

## 0. The proof machinery (one picture)

WS-G is **not a new dispatch path** and **not the proof project**. It is a set of
**measurement + evidence controls** layered onto the existing engine, each
fail-closed and each flag-gated. With `ws_g_proof` OFF the whole surface does not
exist and dispatch behaves exactly as today (SC-003). With it ON, four controls
interlock to answer one question — *"is this delivery actually finished, 0→100?"* —
by evidence only (ED-1), never by a self-report:

```
  SCOPE-LOCK (ED-5/FR-001, §4)                DELIVERY SCORECARD (FR-003/ED-3, §1)
  ── projects/<proof>/SCOPE-LOCK.md (SSOT)     ── evals/e2e/<proof-delivery>/ (golden set)
     Founder-fixed (Q1 = WS-H slice),             6 ED-1 dimensions, each a DETERMINISTIC
     immutable, hash-attributed                    verifier over a REAL artifact
        │  widen/narrow → drift → BLOCK               │  + anti-gaming probe (SWE-bench-style)
        │  ambiguous → [NEEDS CLARIFICATION]          │  unmeasured → SKIPPED, never green (ADR-0020)
        ▼  → halt at Clarify gate (ADR-0014)          ▼
  PROOF PROJECT (FR-005, §3)                    DimensionResult{pass|fail|skipped, evidence_ref}
  ── projects/<proof-name>/ (Placement Law)          │
     lifecycle §2 skeleton, its OWN board,           ▼
     its OWN six AADL gates                    EVIDENCE + ATTESTATION GATE (FR-002,004/ED-1, §2)
        │  no project ticket on org board       ── scripts/check_evidence_gate.py (fail-closed)
        ▼                                          composes: all 6 AADL gates closed +
  runs 0→100 (multi-wave)                           merged PR + green CI per code ticket +
        │                                           committed WaveAttestation (ADR-0031/0032) +
        │  each wave: run_wave → committed           diagnostics 100/100 clean tree +
        ▼  metrics/attestations/<run_id>.json        golden eval + anti-gaming pass
  0→100 DELIVERY (§5)                              │  chains onto ADR-0031/0032 (attest_chain)
  ── local-green NOW (fixture/mock delivery)        ▼  any missing/unmeasured artifact → FAIL
     deploy-to-VM (DAS-1595) INFRA-GATED,       committed metrics/attestations/<run_id>.delivery.json
     carried `blocked` absent a tenant VM        the 0→100 receipt — hash-chained, CI-checked
```

- **[SCOPE-LOCK] (ED-5 / FR-001)** — §4. The proof scope is **Founder-fixed and
  immutable**: no self-widen, no narrow-to-easy. An ambiguous boundary is marked
  `[NEEDS CLARIFICATION]` and **halts at the Clarify gate** (ADR-0014) rather than
  being silently re-scoped.
- **[SCORECARD] (FR-003 / ED-3)** — §1. A golden-eval / SWE-bench-style harness scores
  the delivery against the six ED-1 dimensions; each dimension is a **deterministic
  verifier over a real artifact**; an **anti-gaming probe** fails a delivery that
  pattern-matches the scorecard without real work; an unmeasurable dimension is
  **SKIPPED, never counted green** (ADR-0020). It **extends** `agent_eval.py`/`evals/`
  — it is not a parallel harness.
- **[EVIDENCE GATE] (FR-002,004 / ED-1)** — §2. `check_evidence_gate.py` composes the
  six dimensions into one fail-closed gate, **hash-chains the 0→100 evidence trail
  onto the existing wave attestation** (ADR-0031/0032), and **rejects a false-green** —
  a "done" with a missing or unmeasured artifact.
- **[PROOF PROJECT] (FR-005)** — §3. The proof lives entirely under
  `projects/<proof-name>/` per the lifecycle §2 skeleton, on **its own board**, running
  **its own six AADL gates** — never a ticket on the org `board/tickets/`.
- **[INFRA BOUNDARY]** — §5. The rails (scorecard, evidence gate, skeleton, scope-lock)
  are **buildable + testable NOW** against a committed **fixture/mock delivery**; the
  **live 0→100 run + deploy-to-VM (DAS-1595)** are genuinely infra-gated and carried
  `blocked` absent a real tenant VM — the design does **not** fabricate a proof (no
  false-green).

---

## 1. The golden-eval delivery scorecard (FR-003 / ED-3 / SC-001)

**Requirement (FR-003):** a golden-eval / SWE-bench-style harness MUST score the proof
delivery against the ED-1 completion contract and emit a machine-readable
**run-scorecard**; it MUST **extend the existing eval substrate**
(`scripts/agent_eval.py`, `evals/`, `evals/e2e/`) rather than stand up a parallel
harness; and it MUST include an **anti-gaming probe** so a delivery cannot be scored
green without real artifacts.

### 1.1 Extend, do not fork — where the scorecard lives (ADR-0029)

The landed harness already scores a **role** against a golden task set
(`evals/<role>/<task-id>/`) and already scores a whole **PROJECT-OS pack** end-to-end
(`evals/e2e/`). WS-G adds a **third subject** on the **same** substrate: a **delivery**
scored against the ED-1 completion contract. Concretely (DAS-1591):

- A new golden-set delivery lives under `evals/e2e/<proof-delivery>/` — the same tree
  the WS7 gateway packs already occupy, so it inherits the "score a whole deliverable,
  never a live subagent dispatch" discipline of `evals/e2e/README.md`.
- The runner is a **thin extension of `scripts/agent_eval.py`** — it **reuses** the
  landed primitives verbatim: `load_verifier` (the `verify.py` loader), `clamp01`, the
  `fixtures/` vs `submissions/` anti-gaming boundary, the degenerate-probe machinery
  (`degenerate_credit` / `gaming_findings`), and the deterministic-verifier contract
  (`verify(submission, fixtures) -> float`). It does **not** re-implement scoring,
  gaming defence, or the rubric path. This is the ADR-0029 extend-vs-new posture: a new
  *subject* on an existing *harness*, not a second harness.
- The delivery scorecard is a new dataclass **analogous to `RoleScorecard`** —
  `DeliveryScorecard` — with the **same `to_dict()` machine-readable JSON discipline**,
  so downstream (the evidence gate §2, the maintenance eval DAS-1596) reads one stable
  shape.

### 1.2 The six ED-1 dimensions — each a deterministic verifier over a REAL artifact

The scorecard scores exactly the six dimensions ED-1 names as "finished". Each is a
**`DimensionResult`** — `{dimension, status: pass|fail|skipped, evidence_ref, detail}`
— produced by a **deterministic verifier that reads a committed artifact**, never a
prose claim (ED-3):

| # | ED-1 dimension | Deterministic verifier reads | Reuses (landed) |
|---|---|---|---|
| D1 | **All six AADL gates closed** for the proof project | the proof `README.md` stage-board + each gate's closing artifact under `projects/<proof>/docs/0N-*/`, and `board_lint`/`check_spec_consistency`/`check_dependency_graph` green on the proof board | lifecycle §2 stage-board; the board validators |
| D2 | **Merged PR + green CI per code ticket** | the R-9 counted-completion bar — a merged PR + green CI + T7 pass per delivered ticket | `snapshot_evidence.counted_run_ids` (never re-derived) |
| D3 | **Committed hash-chained wave attestation** | every counted run has a committed `metrics/attestations/<run_id>.json` whose `mechanics` block is complete and whose `attest_chain`/`ledger_hashes` verify | `check_attestation` completeness + integrity |
| D4 | **`diagnostics.py` 100/100 on a clean tree** | the diagnostics score == 100/100 AND `git status` clean (no unstaged/uncommitted drift) | `scripts/diagnostics.py` |
| D5 | **Golden eval passes** | the proof delivery's own golden-set score clears the release bar | `agent_eval` scoring (`PASS_BAR`) |
| D6 | **Anti-gaming probe passes** | §1.3 — the delivery is not gaming the scorecard | `agent_eval.gaming_findings` extended (§1.3) |

The **overall** delivery verdict is **`pass` iff every dimension is `pass`** — a
single `fail` or a single `skipped` denies green (§1.4). The verdict is *conjunctive
and fail-closed*: the completion contract is "AND of all six", not "average of six".

### 1.3 The anti-gaming probe — SWE-bench-style, extending the degenerate probe

The landed harness already refuses a task an **empty** submission can pass
(`gaming_findings` → `degenerate_credit > 0` is a violation) and refuses a task whose
**prompt leaks the answer** (`prompt_leak_findings`). WS-G extends that Goodhart
defence from a *task* to a *delivery*, in the SWE-bench spirit (a patch must make real
failing tests pass, not pattern-match the harness). The probe (DAS-1591) fails a
delivery on any of:

- **Empty/degenerate delivery earns no credit.** A "delivery" with no real diff, no
  merged PR, or an empty artifact set scores 0 — the direct `degenerate_credit`
  inheritance (`MAX_DEGENERATE_CREDIT = 0.0`).
- **A test-gaming model fails (the crux).** A delivery whose "green" tests do **not
  actually exercise the implementation** is gaming. The probe runs a **mutation check**:
  it neutralizes the delivered implementation (empty-body / return-None mutant) and
  asserts the delivery's own test suite **turns RED**. A suite that stays green against
  a gutted implementation is a hard-coded / `assert True` / skipped-test suite — it
  proves nothing, and the probe **fails** it. This is the deterministic analogue of
  "the patch must make a real failing test pass": no real test tension ⇒ no credit.
- **Verifier-leak / answer hard-coding.** A delivery that emits the scorecard's own
  expected outputs (a forged `DeliveryScorecard` JSON, a hand-written attestation, a
  copied evidence snapshot) rather than producing them from real work is caught by the
  **cross-artifact corroboration** the evidence gate already requires (§2.3): the forged
  artifact must *also* forge the independently-committed `metrics/evidence/` snapshot and
  the `attest_chain`, and a mismatch fails. The probe additionally refuses a
  `submissions/` fixture whose graded answer overlaps the agent-visible `task.md`
  (`prompt_leak_findings`, `MAX_PROMPT_LEAK_CREDIT = 0.0`).

The probe is itself part of the golden set (dimension D6), so **a delivery that skips
or disables the probe cannot report green** — the missing probe is a `skipped` D6, and
`skipped` is not a pass (§1.4).

### 1.4 SKIPPED is never green (ADR-0020) — the load-bearing scoring rule

Straight from ADR-0020's "unmeasured is SKIPPED, not green": a dimension whose artifact
is **absent or unmeasurable** returns `status: skipped`, and **`skipped` never counts
toward the pass**. `DeliveryScorecard.passed` is `True` **only** when *every* dimension
is `pass`; any `skipped` or `fail` yields `passed = False`. This forecloses the exact
false-confidence ADR-0020 named: a gate with no data reading as a silent green. The
scorecard reports each dimension's honest tri-state (`pass`/`fail`/`skipped`) with its
`evidence_ref`, so an operator sees *why* a delivery is not green — not a bare boolean.

### 1.5 The run-scorecard shape (illustrative — DAS-1591 owns the schema)

`DeliveryScorecard.to_dict()` (same JSON discipline as `RoleScorecard.to_dict`):

```json
{
  "schema": "daslab.delivery_scorecard.v1",
  "proof": "<proof-name>",
  "run_id": "01J9Z8QK3M7Q0W9E4R5T6Y7U8I",
  "passed": false,
  "dimensions": [
    { "dimension": "aadl_gates_closed", "status": "pass",    "evidence_ref": "projects/<proof>/README.md#stage-board" },
    { "dimension": "merged_pr_green_ci","status": "pass",    "evidence_ref": "counted_run_ids:3" },
    { "dimension": "wave_attestation",  "status": "pass",    "evidence_ref": "metrics/attestations/<run_id>.json" },
    { "dimension": "diagnostics_100",   "status": "pass",    "evidence_ref": "diagnostics:100/100 clean" },
    { "dimension": "golden_eval",       "status": "pass",    "evidence_ref": "evals/e2e/<proof-delivery>" },
    { "dimension": "anti_gaming_probe", "status": "skipped", "evidence_ref": null, "detail": "deploy-to-VM infra-gated; probe not runnable on fixture" }
  ]
}
```

`passed` is `false` because one dimension is `skipped` — the design's whole point:
**the scorecard cannot round an unmeasured dimension up to green.**

**Trace:** a third subject (delivery) on the landed `evals/`/`agent_eval` substrate
(§1.1) → six deterministic ED-1 dimensions over real artifacts (§1.2) → SWE-bench-style
anti-gaming + mutation probe (§1.3) → SKIPPED-never-green conjunctive verdict (§1.4) —
closes **FR-003 / ED-3 / SC-001**.

---

## 2. The 0→100 evidence + attestation gate (FR-002, FR-004 / ED-1 / SC-004)

**Requirement (FR-002/FR-004):** "finished" (0→100) MUST be defined ONLY by evidence,
committed and **hash-chained per ADR-0031/0032**, so a lapse breaks a committed chain
and **fails CI** rather than passing silently; the gate MUST **reject a false-green** —
a "done" with a missing or unmeasured artifact (ADR-0020).

### 2.1 `check_evidence_gate.py` — composing the six dimensions, fail-closed

DAS-1592 builds `scripts/check_evidence_gate.py`, a CI validator in the **same posture**
as the landed `check_attestation.py` (which it reuses, never forks). It does **not**
re-measure the six dimensions — it **composes** the §1 `DeliveryScorecard` with the
already-committed artifacts and applies the conjunctive fail-closed rule:

- **Fail-closed on a claimed-done delivery.** When a delivery is claimed finished (the
  proof project's own GATE-6 is marked closed, or a delivery attestation is emitted),
  the gate requires **every** ED-1 dimension `pass`. A missing merged PR, a missing or
  incomplete `metrics/attestations/<run_id>.json`, `diagnostics != 100/100`, an unclean
  tree, a `skipped` golden eval, or a failing anti-gaming probe → **the gate FAILS CI**.
  There is no "N of 6" partial credit and no averaging.
- **Inert-by-design on an empty board (honest, ADR-0020).** With no claimed delivery
  (a fresh clone, `ws_g_proof` OFF, a no-op wave), there is nothing to require and
  nothing to check — the gate passes cleanly, exactly as `check_attestation` /
  `check_metric_gaming` do. It has **teeth only when a real delivery has committed a
  receipt** (§2.2). It never fabricates a requirement and never scores a phantom pass as
  "verified".
- **Reuse, never re-derive.** The gate reads counted completions via
  `snapshot_evidence.counted_run_ids`, wave-attestation completeness/integrity via
  `check_attestation`, diagnostics via `scripts/diagnostics.py`, and the golden-eval +
  anti-gaming verdict via the §1 scorecard. Every field name is inherited — a rename in
  an upstream producer is caught by a schema-conformance test (the ADR-0031 §"Negative"
  hazard), not silently re-broken.

### 2.2 The committed, hash-chained 0→100 delivery receipt

The gate's teeth are a **committed** receipt, `metrics/attestations/<run_id>.delivery.json`
— a small, redacted, tamper-evident record of the completion verdict, in the **same
committed-artifact class** as the per-wave `metrics/attestations/<run_id>.json`
(ADR-0031 §4). It is **hash-chained onto the wave attestation** so the 0→100 trail is
one continuous chain:

```json
{
  "schema": "daslab.delivery_attestation.v1",
  "proof": "<proof-name>",
  "run_id": "01J9Z8QK3M7Q0W9E4R5T6Y7U8I",
  "created_at": "2026-07-24T12:41:00Z",
  "verdict": "incomplete",
  "dimensions": {
    "aadl_gates_closed": "pass",  "merged_pr_green_ci": "pass",
    "wave_attestation":  "pass",  "diagnostics_100":    "pass",
    "golden_eval":       "pass",  "anti_gaming_probe":  "skipped"
  },
  "counts": { "counted_tickets": 3, "waves": 2 },
  "attest_chain": { "prev": "sha256:7ac2…", "self": "sha256:2b90…" }
}
```

Binding properties (inherited verbatim from ADR-0031 §4):

- **`attest_chain.prev` links to the last wave attestation's `self`.** The delivery
  receipt is the closing bookend on the run's attestation chain: `prev` = SHA-256 of the
  final `metrics/attestations/<run_id>.json` canonical bytes; `self` = SHA-256 of this
  receipt with `self` excluded from its own preimage (the ADR-0023 §2 self-exclusion
  convention). A gap, a re-order, or a tampered receipt **breaks the chain and is
  detectable** — a lapse in the 0→100 trail fails CI, not silently.
- **Small + redacted, COMMITTED (tracked, not gitignored).** It records only structural
  facts — the tri-state per dimension, counts, hashes, ticket ids — never a prompt,
  payload, secret, PII, or PR-URL body (the ADR-0012 / `snapshot_evidence` redaction
  spirit). Like `metrics/evidence/` and `metrics/attestations/`, it enters git history so
  a fresh clone (and therefore CI) can see it; `.gitignore` **must not** cover it.
- **`verdict` is `complete` ONLY when every dimension is `pass`.** A `skipped` (e.g. the
  infra-gated deploy-to-VM, §5) forces `verdict: incomplete` — the receipt itself cannot
  claim "finished" while a dimension is unmeasured.

### 2.3 How the gate rejects a false-green (the FR-004 crux / SC-004)

Two independent committed artifacts must corroborate, so a forged "done" must forge
both — the same bar ADR-0031 set for the wave attestation:

- **Missing artifact ⇒ FAIL.** A delivery claiming done but missing *any* of: a merged
  PR (D2), a committed wave attestation for a counted run (D3), `diagnostics == 100/100`
  on a clean tree (D4), or a golden-eval pass (D5) → the composing gate returns non-zero.
  The claim without the artifact is treated as **false** (ED-3: "a claim without a real
  artifact is treated as false").
- **Skip ≠ pass.** A dimension the delivery reports `skipped` does **not** satisfy the
  gate — `verdict: complete` requires all-`pass`. A "done" with an unmeasured dimension
  is a **false-green** and is rejected (ADR-0020).
- **Cross-check against committed evidence.** The gate asserts the delivery receipt, the
  per-wave attestations, and the P13 `metrics/evidence/<run_id>.json` snapshot **agree**
  (same counted tickets, consistent counts). A forged delivery receipt must also forge
  the wave attestation *and* the evidence snapshot to pass — three committed artifacts
  that must corroborate.
- **Chain integrity.** The `attest_chain` walk recomputes each canonical hash; a broken
  link (a tampered or re-ordered receipt) fails integrity — the same principle
  `check_attestation` / `check_ledger` already apply.

**Trace:** `check_evidence_gate.py` composes the six §1 dimensions fail-closed (§2.1) →
a committed, hash-chained 0→100 delivery receipt onto ADR-0031/0032 (§2.2) →
missing-artifact / skip-is-not-pass / cross-artifact / chain-integrity rejection of a
false-green (§2.3) — closes **FR-002 / FR-004 / ED-1 / SC-004**.

---

## 3. The proof-project skeleton (FR-005 / ED-5 / SC-002)

**Requirement (FR-005):** the proof PROJECT MUST live entirely under
`projects/<proof-name>/`, bootstrapped from the AI-agent-lifecycle §2 canonical
skeleton, and MUST run its OWN six AADL gates; its work tickets MUST live on the
project's own board (`projects/<proof-name>/board-tickets/`), never in the org
`board/tickets/`, and no org-engine WS-G ticket MUST carry a `project:` field (QONUN —
Project Placement Law).

### 3.1 What DAS-1593 bootstraps

DAS-1593 (Development) bootstraps the proof project from the **lifecycle §2 canonical
skeleton** (`governance/policies/ai-agent-lifecycle.md` §2) — the same skeleton the
`evals/e2e/sample-pack` demonstrates. The proof project = the **WS-H control-plane
dashboard slice** (Q1, e.g. the CP-3b trigger-run — the fixed scope, §4):

```
projects/<proof-name>/
├── README.md                  # charter + stage board (the six-gate status log)
├── APPROVED-GOAL-QUEUE.md     # the Founder-approved, research-backed proof goal
├── SCOPE-LOCK.md              # §4 — the Founder-fixed, immutable scope + its hash
├── board-tickets/             # the proof's OWN board — its work tickets live HERE
└── docs/
    ├── 01-planning/  02-design/  03-development/
    ├── 04-testing/   05-deployment/  06-maintenance/
```

- **The proof runs its OWN six AADL gates.** Planning → Design → Development → Testing →
  Deployment → Maintenance, each closed by its lifecycle-§3 gate checklist and logged in
  the proof's `README.md` stage board. This is a **distinct** gate sequence from the
  org-engine WS-G tickets' AADL stages — the org-engine machinery (this doc) is Stage-2
  Design *of the rails*; the proof project runs its own full six-gate delivery *through*
  those rails.
- **Bootstrapped, not hand-authored.** The proof's board tickets are compiled from its
  Founder-approved `APPROVED-GOAL-QUEUE.md` (the QONUN goal-queue law), reusing the
  PROJECT-OS pack + `scripts/gateway_compile.py` machinery `evals/e2e/` already exercises
  — no hand-written proof tickets, zero on the org board.

### 3.2 The Placement Law boundary (structural, not a hope)

Two independent locks keep the proof off the org board:

1. **No `project:` field on any WS-G org-engine ticket.** `board_lint.py` R9 already
   **fails** any `board/tickets/` ticket that declares `project:`. The WS-G tickets
   (DAS-1588…1596) are org-engine tickets (they build the *rails*); none carries a
   `project:` field. The proof's own tickets **do** carry the project binding — but they
   live under `projects/<proof-name>/board-tickets/`, never in `board/tickets/`.
2. **The proof folder is self-contained.** Everything belonging to the proof (code,
   docs, board, scope-lock, evidence) stays inside `projects/<proof-name>/` — deleting
   the proof is a single `rm -rf`. The org-engine WS-G machinery writes **no** project
   content into `docs/`, `scripts/`, or the department trees; it only *measures* the
   proof by reading its committed artifacts.

**Trace:** lifecycle §2 skeleton under `projects/<proof-name>/` with its own board and
its own six gates (§3.1) + the board_lint R9 no-`project:`-field lock + the
self-contained-folder law (§3.2) — closes **FR-005 / ED-5 / SC-002**.

---

## 4. The immutable scope-lock (ED-5 / FR-001 / SC-002)

**Requirement (FR-001):** the proof scope MUST be **fixed by the Founder decision**
(Q1 — the WS-H dashboard slice) and treated as **immutable** by the run: **no
self-scoping** (no widening, no narrowing to what is easy); an **ambiguous boundary**
MUST pass the Clarify gate (ADR-0014) and escalate, **never be re-scoped silently**
(ED-5).

### 4.1 Where the scope is fixed — `projects/<proof>/SCOPE-LOCK.md` (SSOT)

The proof scope is recorded once, at bootstrap (DAS-1593), in a **committed** file
`projects/<proof-name>/SCOPE-LOCK.md`, in the same governance posture as an
`APPROVED-GOAL-QUEUE.md`: it is a **Founder-fixed** record, not runtime state, and
editing it is a `governance_or_policy` + `new_goal`-adjacent change (never
`approval: auto*`, QONUN-5). It carries:

- the **fixed scope statement** (Q1 — the WS-H control-plane dashboard slice, e.g. the
  CP-3b trigger-run) — the exact deliverable boundary, in/out;
- a **Founder-attributed scope hash** — the SHA-256 of the canonical scope statement,
  stamped when the Founder fixes it (the same "attributed, runtime-stamped, not
  agent-writable" discipline WS-E §1.4 applies to a Founder approval event).

### 4.2 No self-widen, no narrow-to-easy — scope-drift is BLOCKED

The scope-lock is enforced, not merely asserted:

- **A widen or a narrow is drift.** The proof board's compiled tickets and its GATE
  checklists are checked against the `SCOPE-LOCK.md` statement (reusing the
  approved-goal-queue check discipline, `scripts/check_approved_goal_queue.py`): a ticket
  or a "done" claim that **exceeds** the fixed scope (self-widen) or that **drops** a
  required part of it to pass more easily (narrow-to-easy) is a **scope-drift violation**
  and **blocks** — it does not silently re-scope. A recomputed scope hash that no longer
  matches the Founder-stamped hash is the tamper signal.
- **The run never re-scopes to stay busy.** ED-4/ED-5: agents never invent new goals or
  trim the goal to look finished. The only sanctioned scope change is a **new
  Founder-fixed `SCOPE-LOCK.md`** (a fresh Founder act), never an agent edit.

### 4.3 An ambiguous boundary halts at the Clarify gate (ADR-0014)

When a scope boundary is genuinely **ambiguous** — the fixed statement does not resolve
whether some behaviour is in or out — the unit **does not guess and does not self-widen
or self-narrow**. It marks the ambiguity `[NEEDS CLARIFICATION]` (ADR-0014), **halts at
the Clarify gate**, and **escalates** (ROUTING.md) for a Founder decision. This is ED-3
("an unknown fact is marked `[NEEDS CLARIFICATION]` and escalated — never resolved by
inventing") applied to scope: an ambiguous boundary is a *clarify*, never a *decide*.

**Trace:** Founder-fixed immutable `SCOPE-LOCK.md` with an attributed hash (§4.1) +
scope-drift (widen/narrow) BLOCK via the reused approved-goal-queue check (§4.2) +
ambiguous-boundary halt at the Clarify gate ADR-0014 (§4.3) — closes **FR-001 / ED-5**.

---

## 5. The infra boundary — buildable NOW, no fabricated proof (SC-002 / SC-003)

**Requirement (FR-006 / Q7):** "shipped" for the proof MUST mean merged to `main` +
green CI + **deployed to the tenant VM**; the deploy-to-VM step is an external
dependency and, absent that infra, MUST be recorded as `blocked` with a precise reason
rather than skipped, faked, or reported green.

The design is split cleanly along the infra line, honestly (the `evals/e2e/README.md`
"proven vs not proven here" discipline):

- **Buildable + testable NOW (local-green).** The scorecard (§1), the evidence gate
  (§2), the skeleton bootstrap (§3), and the scope-lock (§4) are **all buildable and
  unit-testable today** against a **committed fixture/mock delivery** under
  `evals/e2e/<proof-delivery>/` — exactly as `agent_eval` grades offline from recorded
  `submissions/` and the WS7 e2e packs compile into a tmp dir with no live subagent
  dispatch. DAS-1591/1592/1593/1594 deliver and CI-check the rails on this fixture, with
  no VM present. The fixture is **explicitly labeled a fixture** (like the e2e packs
  prove the compiler, not the delivery) — it is **not** a claimed real proof.
- **The live 0→100 run + deploy-to-VM are genuinely infra-gated.** The actual
  end-to-end proof run against a provisioned tenant VM (DAS-1595, Deployment) needs real
  infra (Q7). Absent the VM, DAS-1595 is carried as **`blocked` with the precise reason**
  ("deploy-to-VM requires a provisioned tenant VM; not faked, not skipped") and escalated
  (ROUTING.md, ED-2) — never reported green. In the scorecard, the deploy dimension (and,
  on the fixture, the anti-gaming probe that needs a live run) is honestly **`skipped`**,
  which — per §1.4 / §2.2 — forces `verdict: incomplete`, so the machinery **cannot**
  self-certify a fixture as a shipped proof.
- **No false-green — do NOT design around a fake proof.** The design explicitly refuses
  to let a fixture masquerade as the delivered proof: the evidence gate's SKIPPED-≠-pass
  rule (§2.3) means the fixture run yields `verdict: incomplete` by construction. The
  proof is "shipped" only when the *real* VM deploy closes the deploy dimension — a
  Founder/infra act, not a local green.

**Trace:** rails buildable + CI-checked NOW against a labeled fixture delivery + the
live run/deploy-to-VM genuinely infra-gated and carried `blocked` absent a VM, with the
SKIPPED-≠-pass rule preventing a fixture from self-certifying — closes **FR-006 /
SC-002** and preserves **SC-003** (flag-OFF byte-identical, §7).

---

## 6. Negative-path spec for DAS-1594 (Testing / GATE-4)

The behaviours the Testing ticket (DAS-1594, `zone: tests`,
`implements: [SC-001, SC-003, SC-004]`) must assert. Each is written so it can be
implemented directly against the DAS-1591 `DeliveryScorecard` + `agent_eval` extension,
the DAS-1592 `check_evidence_gate.py` + the delivery receipt, the DAS-1593 skeleton +
`SCOPE-LOCK.md`, and the reused landed surfaces (`check_attestation`,
`snapshot_evidence.counted_run_ids`, `diagnostics.py`, the ADR-0012 redaction spirit),
folded into `tests/test_ws_g_proof_delivery.py`.

### SC-004 — a false-green is REJECTED (the FR-002/FR-004 crux)

- **Missing artifact ⇒ gate FAILS.** For **each** ED-1 dimension in turn, build a
  delivery fixture that is complete **except** that one artifact is absent — no merged
  PR (D2), no committed `metrics/attestations/<run_id>.json` for a counted run (D3),
  `diagnostics == 99/100` or an **unclean tree** (D4), a `skipped`/failing golden eval
  (D5) — and assert `check_evidence_gate.py` returns **non-zero** and the delivery
  receipt's `verdict == "incomplete"`. A "done" with a missing artifact is treated as
  false (ED-3), never green.
- **A scorecard SKIP is not a pass.** Assert a `DeliveryScorecard` with **any**
  dimension `skipped` has `passed == False`, and the composing gate FAILS — `skipped`
  never rounds up to green (ADR-0020, §1.4/§2.3). Assert the all-`pass` fixture is the
  **only** input that yields `passed == True` / `verdict == "complete"`.
- **Chain-integrity break ⇒ FAILS.** Tamper with (or re-order) a delivery receipt's
  `attest_chain`/a wave attestation and assert the gate's integrity walk fails; assert a
  delivery receipt whose `attest_chain.prev` does **not** match the final wave
  attestation's `self` is rejected.
- **Cross-artifact disagreement ⇒ FAILS.** Forge a green `DeliveryScorecard` / delivery
  receipt whose counted-ticket set disagrees with the committed
  `snapshot_evidence.counted_run_ids` / `metrics/evidence/<run_id>.json`, and assert the
  gate's cross-check fails — a forged receipt must also forge the evidence snapshot to
  pass (§2.3).

### SC-001 — the anti-gaming probe fails a gaming model; SKIPPED is honest

- **Empty/degenerate delivery ⇒ 0.** Assert a delivery with no diff / empty artifact set
  scores `0.0` (the inherited `degenerate_credit`), and D6 fails.
- **A test-gaming model FAILS the probe (§1.3).** Build a delivery whose test suite is
  green but does **not** exercise the implementation (an `assert True` / hard-coded /
  all-skipped suite). Assert the **mutation check** neutralizes the implementation and
  the suite **stays green** — and that the probe therefore **fails** the delivery (D6 =
  fail). Assert a delivery whose suite **turns RED** under the mutant passes the probe.
- **Verifier-leak / prompt-leak refused.** Assert a `submissions/` fixture whose graded
  answer overlaps the agent-visible `task.md` scores above `MAX_PROMPT_LEAK_CREDIT` is a
  violation (`prompt_leak_findings`), and a forged-scorecard delivery is caught by the
  §2.3 cross-artifact check.
- **Honest SKIPPED, not a silent green.** Assert an unmeasurable dimension (e.g. the
  infra-gated deploy-to-VM on the fixture) is reported `status: skipped` with an
  `evidence_ref` of `null` and a `detail` reason — and that it is **excluded from
  green**, exactly the ADR-0020 rule.

### SC-003 guard — flag OFF byte-identical (noted for DAS-1594 completeness)

With `ws_g_proof` **OFF** (default), a wave's dispatch behaviour is byte-identical to
pre-merge and the scorecard/harness/evidence-gate is **inert** (SC-003). Assert
`config/features.yaml` carries `ws_g_proof: false`, and that flag-OFF produces a
byte-identical dispatch outcome vs. the surface absent — the WS-G machinery does not
run, emit, or gate when the flag is OFF. This mirrors the WS-A §4 / WS-E §6 flag-OFF
guard and is listed here for DAS-1594 completeness.

### Scope-lock negatives (FR-001 / ED-5 — folded into the same suite)

- **Self-widen BLOCKED.** Assert a proof board that adds a ticket **exceeding** the
  `SCOPE-LOCK.md` statement (a recomputed scope hash ≠ the Founder-stamped hash) is a
  scope-drift violation and blocks (§4.2) — the run does not silently absorb it.
- **Narrow-to-easy BLOCKED.** Assert a "done" claim that **drops** a required part of
  the fixed scope is likewise a drift violation and blocks — a delivery cannot game
  scope down to nothing (ADR-0037 §Enforcement failure-mode (b)).
- **Ambiguous boundary halts at Clarify.** Assert an ambiguous boundary is marked
  `[NEEDS CLARIFICATION]` and routes to the Clarify gate + escalates (ADR-0014), rather
  than being auto-resolved by widening or narrowing (§4.3).

**Hand-off:** SC-004 → §2 (evidence gate) + §1.4 (SKIPPED-≠-green); SC-001 → §1.2/§1.3
(dimensions + anti-gaming probe); SC-003 → §7 (flag-OFF); scope-lock → §4. All
assertions are expressible against the DAS-1591/1592/1593 surfaces, the reused
`check_attestation` / `counted_run_ids` / `diagnostics` primitives, and a committed
fixture delivery — with **no live tenant VM required**.

---

## 7. Traceability matrix

| SPEC FR / SC | ADR-0037 ED | This design | DAS-1594 SC | Builds in |
|---|---|---|---|---|
| FR-001 — proof scope Founder-fixed + immutable; no self-widen/narrow; ambiguous → Clarify | ED-5 | §4 (`SCOPE-LOCK.md` SSOT + attributed hash, drift BLOCK, Clarify halt) | SC-001 (scope negatives) | DAS-1593 |
| FR-002 — "finished" defined ONLY by evidence; unmeasured SKIPPED never green | ED-1 / ADR-0020 | §1.4 (SKIPPED-≠-green) + §2.1 (conjunctive fail-closed gate) | SC-004 | DAS-1592 |
| FR-003 — golden-eval/SWE-bench scorecard extending `agent_eval`/`evals/`; anti-gaming probe | ED-3 | §1 (delivery scorecard on the landed substrate, 6 deterministic dimensions, mutation probe) | SC-001 | DAS-1591 |
| FR-004 — 0→100 evidence committed + hash-chained on ADR-0031/0032; reject false-green | ED-1 | §2 (`check_evidence_gate.py` + delivery receipt chained on `attest_chain`, false-green rejection) | SC-004 | DAS-1592 |
| FR-005 — proof project under `projects/<proof-name>/`, own board, own six gates; no `project:` on org ticket | ED-5 | §3 (lifecycle §2 skeleton bootstrap, board_lint R9 lock, self-contained folder) | (SC-002 via §3) | DAS-1593 |
| FR-006 — shipped = merged + green CI + deployed to VM; deploy-to-VM `blocked` absent infra | ED-2 | §5 (infra boundary; rails local-green NOW, live run/deploy infra-gated, `blocked` not faked) | SC-003 | DAS-1595 |
| FR-007 — WS-G machinery flag-gated `ws_g_proof` DEFAULT OFF; flag-OFF inert | all (flag) | §0 + §6 SC-003 (`ws_g_proof` OFF, byte-identical) | SC-003 | all |
| FR-008 — only legitimate halt is a Founder/AADL gate; blocked unit opens a ticket + escalates | ED-2 | §4.3 (Clarify halt) + §5 (deploy `blocked` + escalate) | (SC-001/SC-003) | DAS-1595 |
| SC-001 — scorecard proves each dimension; unmeasured skipped, never green | ED-1 | §1 | SC-001 | DAS-1591 |
| SC-004 — false-green (missing/unmeasured artifact) caught + fails, proven by a negative test | ED-1 | §2.3 + §6 SC-004 | SC-004 | DAS-1594 |
| SC-005 — diagnostics 100/100, board_lint/spec/dep green, committed attestation, no `project:` field | ED-1 | §1.2 D1/D3/D4 + §3.2 | (all) | all |

## 8. Open items handed downstream (not decided here)

- **DAS-1591** builds the delivery scorecard — the `DeliveryScorecard` dataclass + the
  six ED-1 deterministic dimension verifiers + the SWE-bench-style mutation anti-gaming
  probe, as a **thin extension of `scripts/agent_eval.py`** with the golden set under
  `evals/e2e/<proof-delivery>/` (reusing `load_verifier`, `clamp01`, the
  `fixtures/`/`submissions/` boundary, `gaming_findings`/`prompt_leak_findings`), behind
  `ws_g_proof` OFF. Owns the `daslab.delivery_scorecard.v1` schema.
- **DAS-1592** builds `scripts/check_evidence_gate.py` (composing the six dimensions
  fail-closed, reusing `check_attestation` / `snapshot_evidence.counted_run_ids` /
  `diagnostics.py`) + the committed `metrics/attestations/<run_id>.delivery.json` receipt
  hash-chained onto the wave attestation (`daslab.delivery_attestation.v1`), wired into
  the CI `validate` job alongside `check_attestation`. Adds a schema-conformance test
  (the ADR-0031 field-rename hazard).
- **DAS-1593** bootstraps `projects/<proof-name>/` from the lifecycle §2 skeleton (its
  own `README.md` stage board, `APPROVED-GOAL-QUEUE.md`, `SCOPE-LOCK.md`, and
  `board-tickets/`), reusing the PROJECT-OS pack + `gateway_compile.py` machinery; the
  concrete proof-name and the scope statement are Founder inputs (Q1 = the WS-H dashboard
  slice), not pre-decided here.
- **DAS-1594** implements §6 as `tests/test_ws_g_proof_delivery.py`.
- **DAS-1595** is the Deployment ticket: the real 0→100 run + deploy-to-the-tenant-VM
  (Q7). It is **genuinely infra-gated** (needs a provisioned tenant VM) and, absent it,
  is carried as `blocked` with a precise reason and escalated — never faked, skipped, or
  reported green. The flag flip (`ws_g_proof` ON) is a separate Founder decision once the
  proof slice is demonstrably shipped.
- **DAS-1596** is the Maintenance ticket: the scorecard-health / drift eval (GATE-6).
- **Security Lead (consulted)** reviews the §2 attestation hash-chain integrity (the
  `attest_chain` link onto ADR-0031/0032, the cross-artifact corroboration, the
  redaction of the delivery receipt) against ADR-0012/0031/0032; **CTO (accountable)**
  ratifies GATE-2 closure; **CPO (consulted)** confirms the scorecard is the measurable
  form of the ADR-0037 completion contract.
- The concrete proof-name, the fixed scope statement, and whether/when the live VM run
  happens are **Founder/infra** decisions (Q1/Q7), not pre-decided here.
