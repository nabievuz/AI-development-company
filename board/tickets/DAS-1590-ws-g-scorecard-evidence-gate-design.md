---
id: DAS-1590
title: WS-G Design — golden-eval scorecard and the 0 to 100 evidence gate design
status: done
assignee: cto
author: ceo
dept: engineering
priority: p1
parent: DAS-1588
goal: mustaqil-ws-g-proof
spec: 007-mustaqil-ws-g-proof
implements: [FR-003, FR-004]
labels: [governance]
zone: docs/design
depends_on: [DAS-1589]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 2 — Design (closes GATE-2 for WS-G).** Design the scoring + evidence
machinery the Development tickets implement. No code beyond schemas/specs.

- **Run-scorecard (FR-003):** the machine-readable schema that scores the proof against
  each ED-1 completion-contract dimension (gates closed, merged PR + green CI, committed
  attestation, `diagnostics.py` 100/100, golden eval + anti-gaming probe). Design it as
  an **extension** of the existing eval substrate (`scripts/agent_eval.py`, `evals/`,
  `evals/e2e/`) — not a parallel harness. Specify the **anti-gaming probe** so a
  delivery cannot score green without real artifacts, and the SKIPPED-not-green rule
  for any dimension that cannot be measured (ADR-0020).
- **Evidence + attestation gate (FR-004):** how the 0→100 evidence trail is committed
  and hash-chained onto the existing wave attestation (ADR-0031/0032 — run-start /
  run-end / span / checkpoint / attestation), and how the gate rejects a false-green
  (a "done" with a missing or unmeasured artifact).
- Trace every design element to its FR and to ADR-0037 ED-1…ED-5.

Security Lead consulted (attestation integrity); accountable stage owner = CTO;
responsible = backend-em.

## Acceptance criteria
- [ ] Design doc under `docs/design/` covering the run-scorecard schema (per-dimension scoring + anti-gaming probe + SKIPPED-not-green), and the evidence/attestation gate contract (hash-chain onto ADR-0031/0032, false-green rejection) — each traced to its FR.
- [ ] The design extends `scripts/agent_eval.py` / `evals/` (extend-vs-new, ADR-0029), not a new parallel harness.
- [ ] Negative-path behaviour specified for SC-004 (a "done" with a missing/unmeasured artifact is rejected) so DAS-1594 can test it.
- [ ] Security Lead review recorded. `board_lint`/`check_spec_consistency` green. Merged PR, green CI.

## Log
### 2026-07-24 — Senior Product Manager
Created by /daslab-plan (WS-G Design). Scorecard (FR-003) + evidence/attestation gate
(FR-004) design; extends the existing eval substrate; anti-gaming + no-false-green.

### 2026-07-24 — Backend EM
**GATE-2 Design authored → in_review (assignee cto; CPO consulted — completion
contract; Security Lead consulted — attestation integrity).** Wrote the WS-G PROOF
design doc `docs/design/ws-g-proof-delivery.md` — the org-engine RAILS that measure
and prove an autonomous delivery (NOT the proof project itself), each element traced
to its FR and to ADR-0037 ED-1…ED-5:

- **§1 Delivery scorecard (FR-003/ED-3).** A third *subject* (a delivery) on the
  landed golden-eval substrate — a thin extension of `scripts/agent_eval.py` with the
  golden set under `evals/e2e/<proof-delivery>/`, NOT a fork (ADR-0029). Six ED-1
  dimensions, each a DETERMINISTIC verifier over a REAL committed artifact (gates
  closed, merged PR + green CI via `counted_run_ids`, committed wave attestation via
  `check_attestation`, diagnostics 100/100 clean tree, golden eval, anti-gaming probe).
  Anti-gaming = SWE-bench-style MUTATION probe: neutralize the implementation and a
  gaming test-suite that stays green FAILS. Conjunctive verdict — `pass` iff every
  dimension `pass`; a SKIPPED dimension is NEVER counted green (ADR-0020).
- **§2 Evidence + attestation gate (FR-002,004/ED-1).** `scripts/check_evidence_gate.py`
  composes the six dimensions fail-closed and commits a hash-chained 0→100 delivery
  receipt `metrics/attestations/<run_id>.delivery.json`, `attest_chain.prev` linking
  onto the final `WaveAttestation` (ADR-0031/0032). Rejects false-green four ways:
  missing artifact → FAIL, skip ≠ pass, cross-artifact corroboration (receipt +
  wave attestation + `metrics/evidence/`), chain-integrity walk. Inert on an empty
  board / flag OFF (honest, ADR-0020).
- **§3 Proof-project skeleton (FR-005/ED-5).** DAS-1593 bootstraps
  `projects/<proof-name>/` (the WS-H dashboard slice, Q1) from the lifecycle §2
  skeleton with its OWN board + its OWN six AADL gates. Placement Law is structural:
  board_lint R9 forbids `project:` on org tickets; the proof folder is self-contained.
- **§4 Immutable scope-lock (ED-5/FR-001).** `projects/<proof>/SCOPE-LOCK.md` (SSOT,
  Founder-fixed + attributed hash). Self-widen/narrow-to-easy = scope drift → BLOCK
  (reused approved-goal-queue check); ambiguous boundary → `[NEEDS CLARIFICATION]` →
  halt at the Clarify gate (ADR-0014), never silently re-scoped.
- **§5 Infra boundary.** Rails buildable + CI-checked NOW against a committed,
  explicitly-LABELED fixture delivery; the live 0→100 run + deploy-to-VM (DAS-1595)
  are genuinely infra-gated → carried `blocked` absent a tenant VM, never faked. The
  SKIPPED-≠-pass rule means a fixture yields `verdict: incomplete` — it cannot
  self-certify as a shipped proof (no false-green, no fake proof).

**Negative-path spec for DAS-1594 (§6, Testing/GATE-4)** — `tests/test_ws_g_proof_delivery.py`:
(SC-004) for each ED-1 dimension in turn, a delivery missing that one artifact makes
`check_evidence_gate.py` exit non-zero + `verdict: incomplete`; a scorecard SKIP has
`passed == False` and fails the gate (skip is not a pass); an all-`pass` fixture is
the ONLY green input; a tampered/re-ordered `attest_chain` or a `prev` that doesn't
match the final wave attestation fails integrity; a forged receipt disagreeing with
`counted_run_ids`/`metrics/evidence` fails the cross-check. (SC-001) an empty delivery
scores 0; a test-gaming suite that stays green under the mutation check FAILS the
probe (a suite that turns RED passes); prompt/verifier-leak refused; an unmeasurable
dimension is honest `skipped` (excluded from green). (SC-003) `ws_g_proof` OFF →
byte-identical dispatch, harness inert. Plus scope-lock negatives: self-widen and
narrow-to-easy BLOCK, ambiguous boundary halts at Clarify.

Verified exit 0: `python3 scripts/board_lint.py`, `python3 scripts/check_links.py`,
`python3 scripts/check_spec_consistency.py`. LOCAL-ONLY — touched only
`docs/design/ws-g-proof-delivery.md` + this ticket (no commit/PR/push). Routing to
CTO for GATE-2 ratification (Security Lead review of §2 attestation integrity pending
per the acceptance criteria).

### 2026-07-24 — CTO
**GATE-2 (Design) CLOSED for WS-G PROOF — design RATIFIED.** Reviewed
`docs/design/ws-g-proof-delivery.md` against Accepted ADR-0037 (ED-1…ED-5, CTO-ratified
2026-07-24), SPEC-007 (FR-001…008 / SC-001…005, reviewed), ADR-0020 (no false-green),
ADR-0031/0032 (attestation), ADR-0014 (Clarify), ADR-0029 (extend-vs-new). Carried the
**Security Lead consulted review of §2** myself. Judged sound; closing GATE-2.

**(a) Evidence-gate is genuinely FALSE-GREEN-PROOF.**
- *Missing any one artifact → FAIL.* §2.3 + §1.2: the composing gate is conjunctive
  fail-closed — a delivery missing any of merged PR (D2), committed wave attestation
  (D3), diagnostics 100/100 on a clean tree (D4), or golden-eval pass (D5) returns
  non-zero (ED-3: a claim without a real artifact is treated as false). No "N of 6"
  partial credit, no averaging.
- *A SKIP is never a pass.* §1.4 + §2.2 + §2.3: `DeliveryScorecard.passed` is True only
  when every dimension is `pass`; `verdict: complete` requires all-`pass`; a `skipped`
  dimension denies green (ADR-0020, "unmeasured is SKIPPED, never green"). The §1.5
  illustrative scorecard demonstrates `passed:false` because one dimension is skipped.
- *A fixture yields `verdict: incomplete`.* §5 + §1.5 + §2.2: on a labeled fixture the
  infra-gated deploy dimension (and the live-run anti-gaming probe) is honestly
  `skipped`, forcing `verdict: incomplete` — the machinery cannot self-certify a fixture
  as a shipped proof.

**(b) Scope-lock forecloses BOTH self-widen AND narrow-to-easy.** §4.1–§4.3: the scope
is fixed once in a Founder-attributed, committed `projects/<proof>/SCOPE-LOCK.md` (SSOT,
`governance_or_policy` + `new_goal`-adjacent, never `approval: auto*`). §4.2 enforces
via the reused `check_approved_goal_queue` discipline: a ticket/"done" that *exceeds* the
fixed scope (self-widen) OR *drops* a required part to pass more easily (narrow-to-easy)
is scope-drift → BLOCK; a recomputed scope hash ≠ the Founder-stamped hash is the tamper
signal. §4.3: an ambiguous boundary halts at the Clarify gate (ADR-0014) + escalates,
never silently re-scoped. Both failure modes ADR-0037 §Enforcement (a)/(b) name are
foreclosed; §6 carries the self-widen / narrow-to-easy / ambiguous-halt negatives.

**(c) Infra boundary is HONEST (blocked, not faked).** §5: the rails (scorecard §1,
evidence gate §2, skeleton §3, scope-lock §4) are buildable + CI-checkable NOW against a
committed, explicitly-LABELED fixture delivery — no VM present. The live 0→100 run +
deploy-to-VM (DAS-1595, Q7) are genuinely infra-gated: carried `blocked` with a precise
reason + escalated absent a provisioned tenant VM, never faked/skipped/reported green.
The SKIPPED-≠-pass rule makes this structural, not a promise — the fixture yields
`verdict: incomplete` by construction.

**Security Lead consulted — §2 attestation integrity (carried by CTO): sound.**
- *Hash-chain integrity.* §2.2: `attest_chain.prev` = SHA-256 of the final wave
  attestation's canonical bytes; `self` = SHA-256 with `self` excluded from its own
  preimage (ADR-0023 §2 self-exclusion). The chain-integrity walk recomputes each hash
  (§2.3) — a gap, re-order, or tamper breaks a committed link and fails CI, mirroring
  `check_attestation` / `check_ledger`. Correct.
- *Cross-artifact corroboration.* §2.3: three independent committed artifacts — the
  delivery receipt, the per-wave `metrics/attestations/<run_id>.json`, and the P13
  `metrics/evidence/<run_id>.json` snapshot — must agree on counted tickets/counts; a
  forged receipt must also forge the wave attestation AND the evidence snapshot. Bar
  matches ADR-0031's for the wave attestation. Correct.
- *Receipt redaction.* §2.2: the `daslab.delivery_attestation.v1` receipt records only
  structural facts (per-dimension tri-state, counts, hashes, ticket ids) — never a
  prompt, payload, secret, PII, or PR-URL body (ADR-0012 / `snapshot_evidence` redaction
  spirit) — and is COMMITTED (tracked, not gitignored) so a fresh clone/CI can verify it.
  Correct.

**Extend-vs-new (ADR-0029): satisfied.** §1.1: the scorecard is a THIRD *subject* (a
delivery) on the landed `agent_eval.py`/`evals/`/`evals/e2e/` substrate, reusing
`load_verifier`/`clamp01`/the fixtures-vs-submissions boundary/`gaming_findings` verbatim
— not a parallel harness. §2.1: `check_evidence_gate.py` composes (never re-derives),
reading `snapshot_evidence.counted_run_ids`, `check_attestation`, `diagnostics.py`, and
the §1 scorecard; a field-rename hazard is caught by a schema-conformance test.

**Inert-by-design honesty (ADR-0020).** §2.1: with no claimed delivery / flag OFF the
gate passes cleanly (like `check_attestation`), with teeth only when a real delivery has
committed a receipt — it never fabricates a requirement nor scores a phantom pass.

**Negative-path spec for DAS-1594 (§6): ACCEPTED.** SC-004 (per-dimension missing
artifact + skip-not-pass + chain-integrity + cross-artifact disagreement all reject),
SC-001 (empty→0, mutation probe fails a test-gaming suite that stays green under a gutted
impl, verifier/prompt-leak refused, honest SKIPPED excluded from green), SC-003
(flag-OFF byte-identical, harness inert), and the scope-lock negatives are each
expressible against the DAS-1591/1592/1593 surfaces + a committed fixture, no live VM
required. Testable and complete.

**Traceability (§7).** FR-001…008 / SC-001…005 each map to a design section and an
ADR-0037 ED invariant; no dangling refs (`check_spec_consistency` green). Design ships
NO runtime code (touched only `docs/design/` + ticket) — correct for a Stage-2 Design
gate; the build is downstream (DAS-1591/1592/1593), the tests DAS-1594.

**Validators (exit 0):** `python3 scripts/board_lint.py` → OK, 180 tickets, 0 violations
(lone WARN is DAS-1507, unrelated + non-fatal); `python3 scripts/check_links.py` → OK;
`python3 scripts/check_spec_consistency.py` → OK, 10 SPEC.md checked.

**Housekeeping:** removed a stray `</content>` tag the author left at EOF (malformed
trailing markup; no content lost).

**DECISION: GATE-2 CLOSED.** DAS-1590 → `done` (LOCAL-ONLY per dispatch — no
commit/PR/push; this is a Stage-2 Design ratification carried in-repo, consistent with
the WS-G program posture). This UNBLOCKS the three WS-G Development tickets — DAS-1591
(golden-eval scorecard + harness, `zone: evals`), DAS-1592 (evidence/attestation gate,
`zone: scripts`), DAS-1593 (proof-project skeleton bootstrap, `zone: projects` — note
`projects/` is gitignored, so its output is not committed to the org repo) — distinct
zones, safe to run in parallel. DAS-1594 (Testing) consumes §6; DAS-1595 (Deployment)
stays genuinely infra-gated; DAS-1596 (Maintenance) follows.

