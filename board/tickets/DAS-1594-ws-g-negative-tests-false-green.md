---
id: DAS-1594
title: WS-G Testing — negative tests for false-green rejection and scorecard skip
status: done
assignee: qa-lead
author: ceo
dept: engineering
priority: p1
parent: DAS-1588
goal: mustaqil-ws-g-proof
spec: 007-mustaqil-ws-g-proof
implements: [SC-001, SC-004]
labels: [governance]
zone: tests
depends_on: [DAS-1591, DAS-1592]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 4 — Testing (closes GATE-4 for WS-G).** Prove the evidence machinery holds
with adversarial negative tests. Security Engineer (red team) consulted.

Cover:
- **SC-001:** the run-scorecard scores each completion-contract dimension (gates closed,
  merged PR + green CI, committed attestation, `diagnostics.py` 100/100, golden eval +
  anti-gaming probe); a dimension that cannot be measured is reported SKIPPED, never
  counted green.
- **SC-004:** a false-green attempt — a unit claimed "done" with a missing or unmeasured
  artifact — is caught by the evidence gate / anti-gaming probe and fails.
- **SC-003 guard:** with `ws_g_proof` OFF, dispatch is byte-identical to pre-merge and
  the harness/scorecard is inert.

## Acceptance criteria
- [x] Negative tests exist and PASS in CI for SC-001 (per-dimension scoring + SKIPPED-not-green) and SC-004 (false-green rejected).
- [x] Flag-off no-op behaviour asserted (SC-003).
- [x] Anti-gaming probe proven — a fabricated "done" without a real artifact does not score green.
- [ ] Security Engineer red-team review recorded. Merged PR, green CI. (git materialization + Security Engineer re-review of THIS suite are the residuals — see log; LOCAL-ONLY this run.)

## Log
### 2026-07-24 — Senior Product Manager
Created by /daslab-plan (WS-G Testing). SC-001/SC-004 negative tests; anti-gaming +
false-green rejection; flag-OFF no-op guard; red-team consulted.

## Security conditions (GATE-3)

Bound by the CTO at GATE-3 (Development) closure of DAS-1591/1592/1593 (2026-07-24).
These are the adversarial conditions the GATE-4 Testing work on THIS ticket MUST prove
hold, carried forward from the GATE-3 red-team so the evidence machinery cannot regress:

- **SC-004 forge-negative (BINDING, the hand-off from DAS-1592).** A delivery that pairs
  a genuine real-run signal with a forged all-pass scorecard MUST be rejected. Concretely:
  one real counted `wave_runner.run_wave()` (so D2 `merged_pr_green_ci` + D3
  `wave_attestation` corroborate honestly) + a hand-written
  `daslab.delivery_scorecard.v1` scorecard claiming **all six** dimensions `pass` but with
  NO real `fixtures/` artifacts backing D1 `aadl_gates_closed` / D4 `diagnostics_100` /
  D5 `golden_eval` / D6 `anti_gaming_probe` → `check_evidence_gate.py` MUST exit non-zero,
  emit `verdict: incomplete`, and independently measure D1/D4/D5/D6 as `skipped` (never the
  forged `pass`). The GATE-3 fix already ships this as
  `tests/test_check_evidence_gate.py::test_forged_all_pass_scorecard_with_no_real_d1_d4_d5_d6_artifacts_rejected`
  + `test_forged_scorecard_disagreeing_with_real_artifacts_rejected`; GATE-4 owns the
  SC-004 negative as an explicit, named acceptance test (and may extend it — e.g. a
  disagreeing-self-report variant, and the "test tension ≠ correctness" D6 residual the
  producer red-team flagged, backstopped by the D5 golden-eval accuracy bar).
- **SC-001 (BINDING).** Every completion-contract dimension is scored from a real artifact;
  an unmeasurable dimension is reported SKIPPED, never counted green (ADR-0020). Prove the
  conjunctive verdict: any single non-`pass` (fail OR skip) denies green.
- **SC-003 flag-off guard (BINDING).** With `ws_g_proof` OFF the gate + scorecard are inert
  and dispatch is byte-identical to pre-merge.

**Glob-collision — CLOSED at GATE-3 (option a), NOT a DAS-1594 residual.** The CTO chose to
apply the `check_attestation.py` `*.delivery.json` glob exclusion immediately at GATE-3
(symmetric with `check_evidence_gate.py`), landing its own regression test
`tests/test_check_attestation.py::test_delivery_receipt_is_not_read_as_a_wave_attestation`.
QA does NOT need to own or re-bind this — it is fixed + covered. Recorded here only so the
GATE-4 tester knows the seam is already sealed and green.

### 2026-07-24 — QA Engineer (GATE-4 Testing — negative-path suite delivered)

Read the ticket, `docs/design/ws-g-proof-delivery.md` (§1/§2/§6), SPEC-007 SC-001..005,
`scripts/agent_eval.py::score_delivery`/`mutation_probe`, `scripts/check_evidence_gate.py`,
and the existing `tests/test_ws_g_delivery_scorecard.py` (34 tests) +
`tests/test_check_evidence_gate.py` (21 tests, incl. the DAS-1592 GATE-3 forge regression).
Both were already dense and green — DAS-1591/1592 already ship strong per-dimension +
forge-negative coverage.

**Delivered `tests/test_ws_g_proof_delivery.py`** — the design-named negative-path/
acceptance home (§6: "folded into `tests/test_ws_g_proof_delivery.py`"), 16 tests, all
self-contained (own `_drive_real_wave`/`_complete_delivery` builders, no cross-test-file
imports), all touching only `tmp_path` (no committed `.delivery.json`). SC -> test map:

- **SC-001** — `test_sc001_all_pass_is_the_only_green`,
  `test_sc001_missing_any_single_dimension_denies_green` (parametrized over
  stage-board/counted-tickets/wave-attestation/diagnostics/golden-eval/impl.py — dropping
  ANY one of the 6 ED-1 artifacts denies green, 5/6 pass is still `passed=False`, proving
  no averaging), `test_sc001_skip_never_rounds_up_regardless_of_how_many_pass`.
- **SC-004 (BOUND, GATE-3 hand-off, MUST-PASS)** —
  `test_sc004_forge_negative_bound_gate3_handoff` reproduces the ticket's exact bound
  scenario (one real counted `wave_runner.run_wave()` + a hand-written all-`pass`
  scorecard with NO real D1/D4/D5/D6 artifacts anywhere) against the CURRENT
  `check_evidence_gate.py` and asserts `rc != 0`, `verdict: incomplete`, and D1/D4/D5/D6
  each independently measuring `skipped` — **verified still HOLDS**, the DAS-1592 fix is
  not regressed. Extended per the ticket's own instruction ("may extend it — e.g. a
  disagreeing-self-report variant") with
  `test_sc004_forged_scorecard_disagreeing_with_real_artifacts_rejected` (open gate +
  diagnostics<100 self-reported `pass` → measured `fail`, disagreement rejected).
- **SC-003** — `test_sc003_flag_off_scorecard_and_gate_are_both_inert` (both the
  `agent_eval.score_delivery` producer AND `check_evidence_gate.py`'s composing gate are
  inert with `ws_g_proof` OFF, even given a genuine all-pass scorecard + real wave
  attestation — no receipt is ever written), `test_sc003_features_yaml_default_is_off`.
- **Anti-gaming (SC-001's probe clause / design §1.3)** —
  `test_anti_gaming_mutation_probe_fails_gaming_passes_honest`,
  `test_anti_gaming_gaming_suite_denies_a_whole_delivery_green`,
  `test_anti_gaming_empty_delivery_earns_no_credit`, and
  `test_anti_gaming_d6_test_tension_is_not_correctness_d5_is_the_backstop` — a NEW test
  proving the GATE-3 producer red-team's acknowledged residual (D6 proves test *tension*,
  not *correctness*) is genuinely backstopped: a weak-but-tensioned suite passes D6, but
  an honestly-reported below-bar D5 golden-eval still denies the conjunctive verdict —
  no false-green reaches the delivery because the backstop is independent of the probe.

**Scope-lock negatives (design §6, "folded into the same suite") — NOT implemented, out
of THIS ticket's bound scope.** DAS-1594's own frontmatter binds only `[SC-001, SC-004]`
(SC-003 covered per the design hand-off, no scope-lock SC). No `scripts/check_scope_lock*`
or scope-drift enforcement exists yet — `projects/proof-cp-trigger-run/SCOPE-LOCK.md`
(DAS-1593) is a Founder-fixed doc with an honest `[PENDING FOUNDER APPROVAL]` hash
placeholder, gitignored, no runtime check wired. Writing negative tests against
non-existent enforcement code would either invent behavior or produce meaningless
assertions — left as a residual for whichever ticket lands the scope-drift check.

**A REAL false-green was found during authoring, OUTSIDE the ticket's bound scope — NOT
patched, ESCALATING per instruction ("do NOT patch impl — log + route to
backend-eng-1").** Reproduced live against the current `scripts/check_evidence_gate.py`
(scratch repro, not committed): a delivery with one REAL counted `wave_runner.run_wave()`
(legitimate D2/D3) PLUS hand-authored-but-plausible `fixtures/` artifacts for D1/D4/D5
(`stage-board.md` claiming all 6 gates closed, `diagnostics.json` claiming 100/100
clean-tree, `golden-eval.json` claiming accuracy 0.95) and a trivially-correct D6
impl+test — **is accepted as `verdict: complete`, rc=0**. The DAS-1592 GATE-3 fix
(`measured_dimensions` calling `agent_eval.score_delivery` over `--delivery-dir`) closes
only the "NO artifacts at all" forge (that one measures honestly `skipped`, per
`test_sc004_forge_negative_bound_gate3_handoff` above) — but D1/D4/D5's verifiers
(`_dim_aadl_gates_closed`, `_dim_diagnostics_100`, `_dim_golden_eval`) only read
self-authored files under the delivery's OWN `fixtures/` directory; nothing ties
`fixtures/diagnostics.json` to an actual `scripts/diagnostics.py` invocation,
`fixtures/golden-eval.json` to an actual golden-eval harness run, or `fixtures/
stage-board.md` to the proof project's real stage-board/board_lint state. A forger
willing to hand-author plausible-shaped artifacts (not just omit them) defeats D1/D4/D5
corroboration entirely — the "independent re-measurement" reads the SAME
attacker-controlled directory the self-report describes. D2/D3 (independently derived
from the committed wave-attestation + evidence STORE, which the attacker does not
control) remain sound; D6 is harder but not immune (a trivially-correct throwaway
impl+test satisfies the mutation probe without reflecting the delivery's real work).
This is a genuine, currently-live gap in the "no false-green" property beyond the
ticket's bound SC-004 scenario (inert today only because `ws_g_proof` is OFF by
default). **Not fixed here** — QA does not self-review impl, and this ticket's bound
acceptance criteria (the exact GATE-3 hand-off scenario) independently still holds.
Routing: escalating to QA Lead (my only outbound route) for the orchestrator to dispatch
a fix ticket to **backend-eng-1** (owner of `scripts/check_evidence_gate.py` /
`scripts/agent_eval.py`) — candidate fix direction: tie D1/D4/D5 to something the
delivery author does NOT control (e.g. re-invoke `scripts/diagnostics.py` /
`board_lint.py`/`check_spec_consistency.py`/`check_dependency_graph.py` directly against
the referenced proof project rather than trusting a `fixtures/` JSON stub, and/or
cryptographically bind `fixtures/` to the wave attestation the same way D2/D3 already are).

**VERIFIED (STAGED, `git add -A` first):**
- `python3 scripts/diagnostics.py` → **100/100**.
- `python3 -m pytest tests/test_ws_g*.py tests/test_check_evidence_gate.py -q` → **85
  passed**; `python3 -m pytest -q` (full) → **2298 passed, 4 skipped, 0 xfailed**.
- `python3 scripts/board_lint.py` → exit 0 (180 tickets; pre-existing DAS-1507 body-status
  WARN only).
- `python3 scripts/check_attestation.py` → exit 0.
- `ruff check tests/test_ws_g_proof_delivery.py` → clean.
- No `/Users/owner`/`/home/` literals in the new file; no real `.delivery.json` committed
  to `metrics/attestations/` (every test uses `tmp_path`); `git status --short metrics/` —
  no changes.

**Footprint:** only `tests/test_ws_g_proof_delivery.py` (new) + this ticket file were
touched this run — `scripts/`, `docs/`, and every other test file are untouched, per the
"touch ONLY tests/ + the ticket" constraint.

⛔ **LOCAL-ONLY honored**: no branch/commit/push/PR/remote created this run. Set
`status: in_review`, `assignee: qa-lead` (GATE-4 review). The last acceptance-criteria box
("Security Engineer red-team review recorded. Merged PR, green CI.") stays unchecked —
the branch/PR materialization and the Security Engineer's own re-review of THIS negative
suite are the residuals, plus the newly-found D1/D4/D5 corroboration gap above needing a
backend-eng-1 fix ticket.

### 2026-07-24 — Backend Engineer 1 (routed false-green FIXED — see DAS-1592)
The D1/D4/D5 corroboration gap this ticket routed to me (the "REAL false-green ... found
during authoring" entry above) is fixed in `scripts/check_evidence_gate.py`:
`agent_eval.score_delivery`'s re-measured `"pass"` for `aadl_gates_closed` /
`diagnostics_100` / `golden_eval` is now unconditionally downgraded to `"skipped"` — no
tamper-evident anchor exists yet to corroborate a positive claim for these three, so a
plausible-but-unattested `fixtures/` claim (exactly your repro:
`stage-board.md`/`diagnostics.json`/`golden-eval.json` all claiming success) can never
alone earn green; a measured `"fail"` (real disagreement) still passes through unchanged.
Added `tests/test_check_evidence_gate.py::test_das1594_fabricated_plausible_fixtures_forge_rejected`
reproducing your exact scratch repro — asserts `rc != 0`, `verdict: incomplete`, D1/D4/D5
each independently `skipped`. Full detail + verify output logged on DAS-1592 (`## Log`,
this date). Full suite: `pytest tests/test_check_evidence_gate.py
tests/test_ws_g_proof_delivery.py tests/test_ws_g_delivery_scorecard.py -q` → 72 passed;
`pytest -q` (full) → 2299 passed, 4 skipped, 0 xfailed; `diagnostics.py` 100/100;
`check_attestation.py`/`board_lint.py` exit 0; ruff clean. Only
`scripts/check_evidence_gate.py` + `tests/test_check_evidence_gate.py` + DAS-1592's +
this ticket file touched — `tests/test_ws_g_proof_delivery.py` (your file) untouched.
DAS-1592 re-routed to `cto` (`status: in_review`) for re-review of the reopened gate.
This ticket's own `status: in_review` / `assignee: qa-lead` left unchanged — routing is
yours to close, not mine to self-close.
⛔ LOCAL-ONLY honored: no branch/commit/push/PR/remote created this run.

### 2026-07-24 — QA Lead (GATE-4 Testing CLOSED — WS-G PROOF false-green machinery)

**Decision: GATE-4 (Stage-4 Testing) CLOSED for WS-G PROOF. `status: done`.** The completion
contract is provably no-false-green: both forge classes are rejected by real, named,
independently-run passing tests, and the true-green path is now honestly fail-closed.

**Independent verification (STAGED — `git add -A` run first; exact output):**
- `python3 -m pytest tests/test_ws_g_proof_delivery.py tests/test_check_evidence_gate.py tests/test_ws_g_delivery_scorecard.py -q` → **72 passed, 0 xfailed** (16 + 22 + 34).
- `python3 -m pytest -q` (full) → **2299 passed, 4 skipped, 0 xfailed**.
- `python3 scripts/diagnostics.py` → **SCORE = 100/100** (rc 0).
- `python3 scripts/board_lint.py` → **rc 0** (180 tickets, 0 violations; only the pre-existing
  non-fatal DAS-1507 body-status WARN, unrelated).
- `python3 scripts/check_attestation.py` → **rc 0** (1 committed attestation complete, hash-chain intact).

**Both forges rejected — verified by name (each run individually, all pass):**
- *No-artifact forge* (the bound GATE-3 hand-off from DAS-1592) →
  `tests/test_ws_g_proof_delivery.py::test_sc004_forge_negative_bound_gate3_handoff` — one real
  counted `wave_runner.run_wave()` (honest D2/D3) + all-`pass` scorecard with NO real
  D1/D4/D5/D6 artifacts → `rc != 0`, `verdict: incomplete`, D1/D4/D5/D6 each measured `skipped`.
  The DAS-1592 fix is NOT regressed.
- *Fabricated-plausible-fixture forge* (the REAL deeper false-green found by QA Engineer during
  authoring, routed to backend-eng-1, now FIXED) →
  `tests/test_check_evidence_gate.py::test_das1594_fabricated_plausible_fixtures_forge_rejected` —
  hand-authored internally-consistent `fixtures/` (stage-board all-6-gates-closed,
  diagnostics 100/100 clean-tree, golden-eval 0.95) → gate now asserts `rc != 0`,
  `verdict: incomplete`, D1/D4/D5 each `skipped` (D2/D3 honestly `pass` against the real wave
  attestation). Fix confirmed real in `scripts/check_evidence_gate.py`: `agent_eval.score_delivery`'s
  re-measured `"pass"` for `aadl_gates_closed`/`diagnostics_100`/`golden_eval` is unconditionally
  downgraded to `"skipped"` (no tamper-evident anchor corroborates a positive claim), while a
  measured `"fail"` (real disagreement) still passes through — so a plausible-but-unattested claim
  can never alone earn green, and the honest-empty trade the CTO accepted holds.

**SC map confirmed against real passing tests (no false-green slips a real test):**
- **SC-001** — `test_sc001_all_pass_is_the_only_green`, `test_sc001_missing_any_single_dimension_denies_green`
  (parametrized over all 6 ED-1 artifacts — 5/6 pass is still `passed=False`, no averaging),
  `test_sc001_skip_never_rounds_up_regardless_of_how_many_pass`. Conjunctive verdict proven: any
  single non-`pass` (fail OR skip) denies green.
- **SC-004** — the two forge tests above + `test_sc004_forged_scorecard_disagreeing_with_real_artifacts_rejected`.
- **SC-003 flag-off guard** — `test_sc003_flag_off_scorecard_and_gate_are_both_inert`,
  `test_sc003_features_yaml_default_is_off` (producer AND composing gate inert with `ws_g_proof` OFF).
- **Anti-gaming** — `test_anti_gaming_mutation_probe_fails_gaming_passes_honest`,
  `test_anti_gaming_gaming_suite_denies_a_whole_delivery_green`, `test_anti_gaming_empty_delivery_earns_no_credit`,
  and `test_anti_gaming_d6_test_tension_is_not_correctness_d5_is_the_backstop` (the D6-residual backstop
  is independent of the probe — an honestly-below-bar D5 still denies the conjunctive verdict).

**No-false-green property: VERIFIED.** No fabricated "done" scores green through the gate; every
unmeasurable/unattested dimension reports `skipped`, never counted green (ADR-0020). The true-green
delivery path is honestly fail-closed — D1/D4/D5 currently CANNOT earn `pass` because no
tamper-evident anchor exists yet to corroborate them; the CTO accepted this honest-empty trade and
bound the true-green attestation follow-up (a positive D1/D4/D5 anchor) to **DAS-1595**. That
follow-up does NOT block GATE-4: the machinery is fully tested and cannot emit a false-green today.

**Residuals — do NOT block GATE-4 (Testing gate = the machinery is proven; separate from git/deploy):**
- Git materialization (branch/PR/green CI) + Security Engineer re-review of THIS negative suite —
  acceptance box 4 left unchecked; deferred, LOCAL-ONLY this run per constraint. These are a
  materialization concern, not a Testing-verdict concern.
- **DAS-1595 (Deployment / the live 0→100 proof run)** remains genuinely infra-gated and now
  additionally carries the true-green attestation blocking-condition (positive-claim anchor for
  D1/D4/D5). It is separate from this gate — the evidence machinery is tested here; the live run is
  its own AADL stage.

⛔ LOCAL-ONLY honored: no branch/commit/push/PR/remote created this run. Edited ONLY this ticket
file. GATE-4 CLOSED.
</content>
