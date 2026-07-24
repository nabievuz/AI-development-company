---
id: DAS-1592
title: WS-G Development — the 0 to 100 evidence and attestation gate, no false-green
status: done
assignee: cto
author: ceo
dept: engineering
priority: p1
parent: DAS-1588
goal: mustaqil-ws-g-proof
spec: 007-mustaqil-ws-g-proof
implements: [FR-002, FR-004]
labels: [governance]
zone: scripts
depends_on: [DAS-1590]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 3 — Development (closes GATE-3 for WS-G, part 2).** Build the 0→100
evidence + attestation gate per the DAS-1590 design.

- **FR-002/ED-1:** enforce that "finished" is evidenced ONLY — the gate reads the
  run-scorecard (DAS-1591) and fails unless every completion-contract dimension is
  actually met (gates closed, merged PR + green CI, committed attestation,
  `diagnostics.py` 100/100, golden eval + anti-gaming probe).
- **FR-004/ADR-0031/0032:** commit + hash-chain the 0→100 evidence trail onto the
  existing wave attestation (run-start / run-end / span / checkpoint / attestation), so
  a lapse breaks a committed chain and fails CI rather than passing silently.
- **No false-green (ADR-0020):** a "done" with a missing or unmeasured artifact is
  rejected; unmeasured is SKIPPED, never green. Reuse the existing attestation
  primitives (ADR-0031/0032) — do not fork a second attestation producer.
- **FR-007:** behind `ws_g_proof` OFF; flag-off = byte-identical to pre-merge.

## Acceptance criteria
- [x] The evidence gate reads the run-scorecard and fails on any unmet/unmeasured completion-contract dimension (FR-002).
- [x] The 0→100 evidence trail is committed + hash-chained onto ADR-0031/0032 attestation; no second/divergent attestation producer (FR-004).
- [x] A false-green (missing/unmeasured artifact) is rejected — the hand-off case for DAS-1594's SC-004 test.
- [x] Behind `ws_g_proof` OFF; `diagnostics.py` 100/100 locally.
- [ ] Merged PR, green CI — **not done this run**: dispatch was LOCAL-ONLY (no git branch/commit/push/PR per explicit constraint); see Log for the required follow-up.

## Log
### 2026-07-24 — Senior Product Manager
Created by /daslab-plan (WS-G Development, part 2). FR-002/FR-004 evidence + attestation
gate; reuses ADR-0031/0032; no false-green (ADR-0020); behind `ws_g_proof` OFF.

### 2026-07-24 — Backend Engineer 1
Built `scripts/check_evidence_gate.py` per the DAS-1590 design (`docs/design/ws-g-proof-delivery.md`
§2) + ADR-0037 ED-1/ED-4 + ADR-0020/0031/0032. Behind `ws_g_proof` (`config/features.yaml`,
default OFF) — flag-off is byte-identical/inert (no read, no write).

**FR/ED → file + test map:**
- **FR-002 / ED-1** (fail-closed composition of the run-scorecard's six dimensions) →
  `scripts/check_evidence_gate.py::dimension_statuses` / `verdict_of` / `corroborate` →
  `tests/test_check_evidence_gate.py::test_dimension_statuses_defaults_missing_to_skipped`,
  `test_verdict_of_any_skip_or_fail_is_incomplete`,
  `test_single_dimension_fail_or_skip_rejects_green[...]` (D1/D4/D5/D6),
  `test_d2_forged_cross_check_rejects_green`, `test_d3_missing_attestation_rejects_green`.
- **FR-004 / ADR-0031/0032** (committed, hash-chained 0→100 receipt onto the existing
  wave-attestation chain; reuses `wave_runner._sha256` / `_attest_self_hash` /
  `_GENESIS_PREV_HASH` and `check_attestation.verify_completeness` / `chain_errors`
  VERBATIM — no forked hashing/attestation logic) →
  `scripts/check_evidence_gate.py::build_receipt` / `write_receipt` / `verify_receipt` /
  `scan_committed_receipts` → `tests/test_check_evidence_gate.py::
  test_all_pass_fixture_writes_complete_receipt`,
  `test_tampered_receipt_self_hash_fails`, `test_tampered_prev_link_fails`,
  `test_dangling_wave_chain_rejects_new_delivery`.
- **No false-green (ADR-0020), the four rejections DAS-1592 must prove:**
  1. Missing artifact → FAIL: `test_d3_missing_attestation_rejects_green` (no committed
     wave attestation for the claimed `run_id` at all) + the single-dimension fail
     parametrization (D1/D4/D6 reported `fail`).
  2. SKIP ≠ pass → FAIL: `test_verdict_of_any_skip_or_fail_is_incomplete` (unit) +
     `missing_d5_skipped.json` fixture case (golden-eval `skipped` still yields
     `verdict: incomplete`, non-zero exit).
  3. Cross-artifact corroboration → FAIL: `test_d2_forged_cross_check_rejects_green`
     (scorecard claims `merged_pr_green_ci: pass` against a driven wave whose committed
     evidence has 0 counted completions — the D2 dimension is downgraded to `fail` and
     the gate rejects) + `test_forged_counts_disagreeing_with_evidence_fails` (a
     post-hoc hand-tampered `counts.counted_tickets` disagreeing with the committed
     evidence is caught by `verify_receipt`'s re-derivation, never trusted from the file).
  4. Chain-integrity walk → FAIL: `test_tampered_receipt_self_hash_fails` (post-write
     tamper breaks the self-hash), `test_tampered_prev_link_fails` (re-pointed `prev`),
     `test_dangling_wave_chain_rejects_new_delivery` (the referenced wave attestation
     itself is tampered → D3 downgraded to `fail`).
- **Inert-by-design** (empty board / flag OFF, ADR-0020 "honest empty"):
  `test_flag_off_inert_even_with_a_scorecard`, `test_no_scorecard_inert_on_empty_board`
  — no receipt is ever written when there is nothing claimed done.
- **Empty/degenerate delivery scores 0:** `test_empty_delivery_scores_zero`
  (`dimensions: []` → every dimension defaults `skipped`/`fail`, never `pass`).
- **Schema-conformance guard** (the ADR-0031 field-rename hazard, design §"open items"):
  `test_six_dimension_names_are_fixed` pins `SIX_DIMENSIONS` + `DELIVERY_SCHEMA` +
  `SCORECARD_SCHEMA` so an upstream (DAS-1591) rename is caught, not silently re-broken.

**Design decision (not pre-decided by DAS-1590):** DAS-1591 (the `DeliveryScorecard`
producer) is still `status: todo` as of this run (concurrent WIP in this same tree —
`scripts/agent_eval.py` / `evals/e2e/proof-delivery-fixture/` are its in-flight files, not
touched by this ticket). Since the gate's job is to COMPOSE the scorecard, not produce it,
`check_evidence_gate.py` consumes the run-scorecard strictly as a committed/loadable
`daslab.delivery_scorecard.v1` JSON document (schema-tag checked, `SCORECARD_SCHEMA`
constant) rather than importing a DAS-1591 Python type — this decouples the two tickets
cleanly and matches "reuse the chain logic, don't fork" (only `check_attestation` /
`wave_runner` primitives are imported, never `evals`/`agent_eval`).

**Fixtures:** `tests/fixtures/ws_g_evidence_gate/` — 8 LABELED scorecard JSON fixtures
(README.md explains each), never presented as a real delivery. Every wave-attestation +
evidence artifact the tests corroborate against is produced by a REAL
`wave_runner.run_wave()` drive into a `tmp_path` tree (mirrors
`tests/test_check_attestation.py`'s own `_drive` helper) — no hand-typed attestation.

**Verify (staged, `git add -A` first):** `python3 scripts/diagnostics.py` → 100/100;
`python3 -m pytest` → 2279 passed, 4 skipped (full suite, including the new 19-test
`tests/test_check_evidence_gate.py`); `python3 scripts/check_attestation.py` → exit 0,
unmodified/unbroken (no `.delivery.json` was ever committed to the real
`metrics/attestations/`, only to `tmp_path` trees in tests, so its `*.json` glob never
collided with a delivery receipt); `python3 scripts/board_lint.py` → exit 0 (180 tickets,
1 pre-existing non-fatal WARN unrelated to this ticket); `ruff check scripts tests` →
clean (my two new files are clean; a stray unused-import in `scripts/agent_eval.py` seen
mid-run belonged to DAS-1591's concurrent in-flight edit, not mine, and was gone by the
time the full gate ran).

**Discovered cross-cutting concern (flagging, not deciding):** `check_attestation.py`'s
`attest_dir.glob("*.json")` will ALSO match a real, future `<run_id>.delivery.json` once
one is genuinely committed to `metrics/attestations/` (a delivery receipt is a valid JSON
document but the wrong schema tag) — it would then report a false `check_attestation`
FAIL for that file. This ticket avoided the collision by never committing a real receipt
into the tracked directory (only `tmp_path` fixtures in tests), per the "reuse
`check_attestation.py` read-only" constraint. Before DAS-1595 (the live 0→100 run) ever
writes a real `metrics/attestations/<run_id>.delivery.json`, `check_attestation.py`'s glob
needs a small follow-up (e.g. excluding `*.delivery.json`, or filtering by schema tag) —
routed to Backend EM for triage/ticketing, not decided here.

**Footprint:** `scripts/check_evidence_gate.py` (new), `tests/test_check_evidence_gate.py`
(new, 19 tests), `tests/fixtures/ws_g_evidence_gate/` (new, 8 labeled JSON fixtures +
README). No edits to `evals/`, `scripts/agent_eval.py`, `projects/`, or
`scripts/check_attestation.py` / `scripts/wave_runner.py` (read-only reuse).

**LOCAL-ONLY constraint honored:** no git branch/commit/push/PR created this run (explicit
dispatch constraint). This deviates from the standard "one issue = one branch = one PR"
git rule (`engineering/AGENTS.md` §2) — flagging so Backend EM/orchestrator can materialize
the branch + PR from this working tree's diff before merge; `status: in_review` /
`assignee: backend-em` reflects code-complete + self-verified, NOT a green-CI merged PR.

### 2026-07-24 — Security Engineer (GATE-3 red-team, blocking) — FAIL: forged green accepted
Red-teamed the evidence + attestation gate (`scripts/check_evidence_gate.py`).
Ran `pytest tests/test_check_evidence_gate.py` (19 pass) + ephemeral forge-a-green
probes (scratch, deleted; **committed no `.delivery.json` to the tracked
`metrics/attestations/`** — all forges ran in tmp trees).

| Probe | Verdict | Evidence |
|---|---|---|
| Forged receipt (hand-write a complete `daslab.delivery_attestation.v1` into the store, then scan) | HOLDS | `scan_committed_receipts`→`verify_receipt` recomputes the self-hash → mismatch → gate exits 1. |
| Tampered chain / mismatched `prev` | HOLDS | `verify_receipt` recomputes `prev` vs the referenced wave attestation's canonical bytes; `check_attestation.chain_errors` walks the whole store. |
| Missing artifact (no committed wave attestation for the claimed `run_id`) | HOLDS | `corroborate` downgrades D3 `wave_attestation`→`fail`; forged all-pass scorecard with no attestation → exit 1 (ran live). |
| Empty / inert (flag OFF, or no scorecard) | HOLDS | flag-gate returns exit 0, writes nothing; no scorecard → inert exit 0. |
| **Integration seam (D1/D4/D5/D6 corroboration)** | **HOLE — CRITICAL** | **The gate independently re-derives ONLY D2 (counted completions) and D3 (chain walk). D1 `aadl_gates_closed`, D4 `diagnostics_100`, D5 `golden_eval`, D6 `anti_gaming_probe` are trusted VERBATIM from the scorecard's self-reported `status` — never re-measured, never corroborated against a committed artifact. A forged green is accepted.** |

**Overall gate verdict: FAIL (forged green accepted).**

**The exact forge (reproduced live, exit 0 + `verdict: complete` + committed receipt):**
1. Drive ONE real counted `wave_runner.run_wave()` (exactly what any genuine 0→100 run
   already produces) → a legit committed wave attestation with real counted completions,
   so D2 + D3 corroborate honestly.
2. Hand-write the `--scorecard` JSON (schema `daslab.delivery_scorecard.v1`, correct
   `run_id`) with **all six** dimensions `status: "pass"` — but supply NO real artifacts
   for D1/D4/D5/D6 (no closed stage-board, no `diagnostics 100/100`, no golden-eval run,
   no mutation probe). i.e. diagnostics could be 40/100, a gate open, the suite gameable.
3. Run the gate → it takes D1/D4/D5/D6 = `pass` from the scorecard verbatim, D2/D3
   corroborate against the real attestation → `verdict_of` = **complete** → exit 0 and a
   hash-chained `<run_id>.delivery.json` receipt is committed certifying a bogus 0→100.

Root cause: the gate reads the scorecard as an **unauthenticated serialized JSON doc**
(schema-tag checked only) and re-corroborates just 2 of 6 dimensions. The asymmetry is the
tell — the authors already knew a self-report can't be trusted for D2/D3 (hence the
independent re-derivation), but left D1/D4/D5/D6 as pure self-report. This directly
violates the ticket's own ED-1 contract ("finished is evidenced ONLY, never a
self-report") for **four of six** dimensions. Whoever produces the `--scorecard` input
(any agent in the 0→100 run) controls those four with zero corroboration; the receipt's
hash-chain protects the receipt bytes *after the fact*, not the scorecard's provenance.

**Required fix (pick one; author's call — do NOT self-review, re-route to a reviewer):**
- **(A) Re-measure, don't trust.** The gate re-invokes `agent_eval.score_delivery` over
  the committed delivery dir (or reads the committed D1/D4/D5/D6 artifacts directly) and
  requires ITS `DimensionResult`s, instead of trusting the loose scorecard's statuses —
  extend the D2/D3 corroboration pattern to all six. Cleanest; closes the seam fully.
- **(B) Bind the scorecard into the integrity chain.** Require the scorecard to be a
  committed artifact whose canonical bytes are hash-chained/attested in the same wave
  chain, so a hand-edited scorecard breaks the chain walk. (May pull a small follow-up
  into DAS-1591 to make `score_delivery` emit a self-attesting scorecard.)
- Whichever path: add a regression test = the forge above (real attestation + forged
  D1/D4/D5/D6 scorecard) MUST exit 1. Hand this to DAS-1594 as its SC-004 negative.

**Glob-collision (flagged for CTO, NOT a blocker, NOT my fix):** `check_attestation.py:242`
`attest_dir.glob("*.json")` will match a future `<run_id>.delivery.json`. **Not a live
risk now** — `git ls-files '*.delivery.json'` = empty; only `01KWS8ATTEST…json` (a wave
attestation) is committed; `check_attestation.py` exits 0. It is a **forward-looking**
follow-up (bites when DAS-1595 writes the first real receipt). **Cannot be abused to forge
a green** — the collision makes `check_attestation` err toward a false FAIL (wrong schema
→ rejected), i.e. fail-closed, never lax. Note the gate itself already excludes
`.delivery.json` in its own glob (`check_evidence_gate.py:192`); only the standalone
`check_attestation.py` needs the same exclusion/schema-filter. Route to CTO/Backend EM.

**Disposition:** REAL HOLE (CRITICAL — a false-green is never passed). `status: in_review`
kept; `assignee` → `backend-eng-1` (dev owner) for the fix. AC "false-green rejected"
(FR-002) is NOT met as built. Verify after my edits: `board_lint.py` exit 0,
`check_attestation.py` exit 0 (I edited only ticket files; committed no receipts).

### 2026-07-24 — Backend Engineer 1 (GATE-3 red-team hole — FIXED, option A)
Fixed the CRITICAL false-green hole the GATE-3 red-team found. `scripts/check_evidence_gate.py`
no longer trusts the caller-supplied `--scorecard`'s self-reported `status` for ANY of the six
ED-1 dimensions — it independently re-measures all six from real committed artifacts, exactly
matching the red-team's option A ("re-measure, don't trust").

**What changed:**
- **D2 `merged_pr_green_ci` / D3 `wave_attestation`** — UNCHANGED. These were already
  independently re-derived from the committed wave-attestation + evidence store
  (`corroborate()`'s existing logic); this is the stronger of the two signal sources
  (real committed store vs. a `fixtures/` snapshot) so it stays authoritative for those two.
- **D1 `aadl_gates_closed` / D4 `diagnostics_100` / D5 `golden_eval` / D6 `anti_gaming_probe`**
  — NEW: `scripts/check_evidence_gate.py::measured_dimensions()` invokes
  `agent_eval.score_delivery(delivery_dir, enabled=True)` (DAS-1591's six deterministic,
  artifact-only dimension verifiers — reused READ-ONLY, `scripts/agent_eval.py` untouched)
  over a `--delivery-dir` (new CLI flag; default = the `--scorecard` file's parent
  directory). `corroborate()` now REPLACES the scorecard's self-reported status for these
  four dimensions outright with the measured `DimensionResult.status` — a caller-supplied
  `"pass"` with no real backing `fixtures/{stage-board.md,diagnostics.json,golden-eval.json,
  impl.py,test_impl.py}` artifact measures `"skipped"` (agent_eval's own "missing artifact ⇒
  SKIPPED, never pass" rule) and is never accepted. Any disagreement between the self-report
  and the measured status is also appended to `errors` (surfaced in the FAIL output for audit),
  which alone forces the overall verdict to FAIL even if the composed per-dimension statuses
  happened to read complete.
- Preserved everything that already held: D2/D3 re-derivation, receipt hash-chain
  (`build_receipt`/`verify_receipt`/`scan_committed_receipts` untouched), cross-artifact
  corroboration, SKIP≠pass (`verdict_of` untouched), missing-artifact→FAIL, flag-off inert
  (`_flag_gate_inert` untouched, byte-identical when `ws_g_proof` OFF).

**Regression tests added** (`tests/test_check_evidence_gate.py`, now 21 tests, +2 new):
- `test_forged_all_pass_scorecard_with_no_real_d1_d4_d5_d6_artifacts_rejected` — the EXACT
  red-team forge reproduced: one real counted `wave_runner.run_wave()` (legit D2/D3) + a
  hand-written `all_pass.json`-style scorecard claiming all six `pass`, but with NO real
  `fixtures/` artifacts anywhere for D1/D4/D5/D6. Asserts `rc != 0`, `verdict: incomplete`,
  D2/D3 read `pass` (honest, real), D1/D4/D5/D6 each independently measure `skipped` (never
  the forged `pass`) — the forge is dead.
- `test_forged_scorecard_disagreeing_with_real_artifacts_rejected` — a scorecard forging
  D1/D4 `pass` while the real committed `fixtures/` show an open gate / diagnostics < 100:
  rejected, measured `fail` wins over the self-report.
- Updated the 8 existing scenario tests (`test_all_pass_fixture_writes_complete_receipt`,
  the 4-way `test_single_dimension_fail_or_skip_rejects_green` parametrization, D2/D3
  isolation tests, and the 3 chain-tamper tests) to also write real `fixtures/` delivery
  artifacts via the new `_write_delivery_fixtures()` test helper, so each scenario's intended
  single failure point is genuinely backed by (or genuinely missing) a real artifact rather
  than relying on a self-report the gate no longer trusts. No existing fixture JSON in
  `tests/fixtures/ws_g_evidence_gate/` was modified — only `tests/test_check_evidence_gate.py`
  changed, per the LOCAL-ONLY footprint constraint.

**Verify (staged, `git add -A` first):**
- `python3 -m pytest tests/test_check_evidence_gate.py tests/test_ws_g_delivery_scorecard.py -q`
  → 21 + 34 = 55 passed (the 2 new forge-regression tests pass, all 19 prior tests green).
- `python3 -m pytest -q` (full suite) → **2281 passed, 4 skipped, 0 xfailed** (was 2279
  passed/4 skipped before this fix; +2 for the new tests).
- `python3 scripts/diagnostics.py` → **100/100**.
- `python3 scripts/check_attestation.py` → exit 0 ("1 committed attestation(s) complete
  ... hash-chain intact"); unmodified — still no `.delivery.json` in the tracked
  `metrics/attestations/`.
- `python3 scripts/board_lint.py` → exit 0 (180 tickets; 1 pre-existing non-fatal WARN on
  DAS-1507, unrelated to this ticket).
- `ruff check scripts/check_evidence_gate.py tests/test_check_evidence_gate.py` → clean.
- `grep -n "/Users\|/home/"` over both touched files → no hits. No secret-shaped strings
  introduced.

**Footprint (per the LOCAL-ONLY dispatch constraint):** only
`scripts/check_evidence_gate.py`, `tests/test_check_evidence_gate.py`, and this ticket file
were touched this run. `scripts/agent_eval.py`, `evals/`, and other tickets were NOT modified
(DAS-1591's `score_delivery` is imported and called, never edited).

**Disposition:** GATE-3 red-team CRITICAL hole CLOSED. `status: in_review`, `assignee` →
`cto` (re-routing for GATE-3 re-review per the red-team's own instruction to re-route to a
reviewer, not self-close). **LOCAL-ONLY constraint honored again this run** — no git
branch/commit/push/PR created; the standing gap from the prior log entry (materialize a
branch + PR from this working tree before merge) still applies and is unresolved by this run.

### 2026-07-24 — CTO (GATE-3 Development closure — part 2 of 3; forge CONFIRMED dead)
**GATE-3 CLOSED for WS-G. This ticket → `done`.** Re-reviewed the backend-eng-1 fix as the
GATE-3 accountable owner and independently confirmed the CRITICAL false-green hole is dead.

**Read `scripts/check_evidence_gate.py` end-to-end — all six ED-1 dimensions are now
artifact-derived, none self-reported:**
- **D1 `aadl_gates_closed` / D4 `diagnostics_100` / D5 `golden_eval` / D6
  `anti_gaming_probe`** — `measured_dimensions()` invokes `agent_eval.score_delivery(
  delivery_dir, enabled=True)` and `corroborate()` REPLACES the caller's status outright
  (`statuses[dim] = measured_status`, line ~253); the scorecard's self-report is used
  ONLY to detect disagreement (appended to `errors`, which alone forces FAIL). A missing
  artifact measures `skipped` (ADR-0020), never the forged `pass`.
- **D2 `merged_pr_green_ci` / D3 `wave_attestation`** — unchanged: independently
  re-derived from the committed wave-attestation + evidence store (D3→`fail` if no
  committed attestation for the `run_id`; D2→`fail` if it claims `pass` but committed
  evidence shows 0 counted completions). This is the stronger of the two sources, kept
  authoritative.
- `verdict_of` = `complete` iff all six are `pass` (conjunctive; SKIP ≠ pass). Receipt
  hash-chain (`build_receipt`/`verify_receipt`/`scan_committed_receipts`) intact.

**Forge dead — independently verified (STAGED, `git add -A` first):**
- `pytest tests/test_check_evidence_gate.py -q -k forged` → **4 passed** (the exact
  red-team forge: one real counted `wave_runner.run_wave()` for legit D2/D3 + an all-pass
  scorecard with NO real D1/D4/D5/D6 `fixtures/` artifacts → D1/D4/D5/D6 each measure
  `skipped`, `verdict: incomplete`, `rc != 0` — the forge cannot reach green).
- `pytest tests/test_check_evidence_gate.py tests/test_ws_g_delivery_scorecard.py -q` →
  **55 passed**; `pytest -q` (full) → **2282 passed, 4 skipped, 0 xfailed**.
- `diagnostics.py` → **100/100**; `check_attestation.py` → exit 0; `board_lint.py` → exit 0.

**Glob-collision follow-up — RESOLVED, option (a) (CTO call).** `check_attestation.py`'s
`attest_dir.glob("*.json")` would have matched a future `<run_id>.delivery.json` and
mis-read it as a malformed wave attestation (a false FAIL) once DAS-1595 writes the first
real receipt. Fail-closed, no live risk now (`git ls-files '*.delivery.json'` empty), but a
forward-looking footgun. I applied the small exclusion NOW (skip `*.delivery.json` in the
glob — symmetric with `check_evidence_gate.corroborate()`'s own wave-file glob) plus a
regression test `test_delivery_receipt_is_not_read_as_a_wave_attestation`. Edited ONLY
`scripts/check_attestation.py` + `tests/test_check_attestation.py` (14 tests pass, ruff
clean). WS-G impl otherwise untouched.

**LOCAL-ONLY closure note:** `done` here = the AADL **GATE-3 (Development)** gate is closed
on verified-local-green by the accountable owner. AC "Merged PR, green CI" (last box)
stays honestly unchecked — the branch + PR materialization from this working tree + green
CI is the one residual, owned by Backend EM / orchestrator, and is NOT a re-open of the
development gate. Unblocks DAS-1594 (GATE-4 Testing), whose SC-004 negative binds this
forge (see the `## Security conditions (GATE-3)` section I appended to DAS-1594).

### 2026-07-24 — Backend Engineer 1 (DEEPER GATE-4 hole, DAS-1594 hand-off — FIXED)
Closed the DEEPER false-green hole QA (GATE-4, DAS-1594) reproduced live: the prior
GATE-3 fix wired D1/D4/D5/D6 to `agent_eval.score_delivery()`, but that harness's D1
(`_dim_aadl_gates_closed`) / D4 (`_dim_diagnostics_100`) / D5 (`_dim_golden_eval`)
verifiers only read self-authored files under the delivery's OWN `fixtures/` dir
(`stage-board.md`, `diagnostics.json`, `golden-eval.json`). A deliverer willing to
hand-author *plausible* content (not just omit the files, which already measured
`skipped`) made `score_delivery` report a genuine "pass" for these three with zero
independent backing — the "independent re-measurement" was reading the SAME
attacker-controlled directory the self-report describes. QA reproduced this live
(scratch repro, not committed): a real counted wave + `fixtures/{stage-board.md
claiming all six gates closed, diagnostics.json claiming 100/100, golden-eval.json
claiming accuracy 0.95}` + a trivially-correct D6 impl/test → accepted as
`verdict: complete`, rc=0.

**Fix — chose the workable half of Option (A)/(B), scoped to `check_evidence_gate.py`
only (per the dispatch's hard file constraint; `agent_eval.py`/`evals/` untouched).**
Audited both options against the ACTUAL repo state before picking:
- **Option A** ("corroborate against the committed, attested evidence chain") requires
  the wave attestation / `metrics/evidence/<run_id>.json` to actually RECORD a
  diagnostics score / gate state / golden result to match against. Confirmed by reading
  `wave_runner.py`'s attestation payload + `snapshot_evidence.build_run_evidence`: NEITHER
  carries those three facts today (they only carry counted-completion + chain-integrity
  data). Extending that schema is a `wave_runner.py`/`snapshot_evidence.py` change — out
  of this ticket's file scope.
- **Option B** ("re-run the real validators") — tried re-invoking `scripts/diagnostics.py`
  /`board_lint.py`/the golden-eval roster for real, but confirmed live that these are
  ENGINE-WIDE invariants (fixed `REPO_ROOT`, no per-delivery scoping) — re-running them
  would make D1/D4/D5 trivially "pass" whenever the org-engine happens to be healthy,
  **regardless of the specific delivery's own claim**, decoupling the dimension entirely
  from what's being delivered and breaking existing tests that expect a delivery's OWN
  bad fixture content to independently fail D1/D4 (verified this would break
  `test_forged_scorecard_disagreeing_with_real_artifacts_rejected` in both test files).

**What shipped instead — the honest fail-closed conclusion Option A's own text implies**
("a claim absent from... the attested anchor -> skipped/fail, never pass"): since NO
tamper-evident anchor exists yet for D1/D4/D5, a `agent_eval.score_delivery`-measured
`"pass"` for these three is now unconditionally downgraded to `"skipped"` in
`check_evidence_gate.py::measured_dimensions()` (new `_UNCORROBORATED_CLAIM_DIMENSIONS`
constant) — a plausible, internally-consistent self-authored claim can never alone earn
green. A measured `"fail"` (the artifact itself shows real badness — an open gate,
diagnostics < 100) is NOT downgraded and passes through unchanged (detecting a lie needs
no corroboration; only trusting a claimed truth does) — so the existing
disagreeing-self-report tests are unaffected. D2/D3 (store-corroborated against the real
committed wave-attestation + evidence) and D6 `anti_gaming_probe` (EXECUTION-verified —
`agent_eval.mutation_probe` actually runs the delivery's suite against a mutated
implementation, not a bare claim) are untouched and can genuinely still reach `"pass"`.
The module docstring now documents this TRUST BOUNDARY exhaustively, including the
explicit residual: making D1/D4/D5 genuinely reach `"pass"` again needs a follow-up that
either extends the attested evidence chain to record these three facts (Option A,
`wave_runner.py`/`snapshot_evidence.py`) or wires a genuine live per-delivery re-run
(Option B, needs a per-project-scoped `diagnostics.py`/golden-eval invocation that
doesn't exist yet) — out of this ticket's scope, flagged for a future ticket, not decided
here.

**Consequence, stated plainly:** `verdict: complete` is currently UNREACHABLE via
`check_evidence_gate.py` for any delivery (D1/D4/D5 can at best be `fail`/`skipped`,
never `pass`) until that follow-up lands. This is an intentional, honest trade —
ADR-0020's "honest empty beats silent green" — not a regression: `ws_g_proof` is OFF by
default and the live 0→100 run (DAS-1595) is independently infra-gated (blocked absent a
tenant VM), so nothing currently depends on reaching `complete` through this gate.

**Regression test added** (`tests/test_check_evidence_gate.py`, now 22 tests, +1 net new):
`test_das1594_fabricated_plausible_fixtures_forge_rejected` — reproduces the QA
Engineer's exact repro verbatim (real counted wave + plausible `fixtures/
{stage-board.md, diagnostics.json, golden-eval.json}` all claiming genuine success, all
internally consistent) and asserts `rc != 0`, `verdict: incomplete`, D1/D4/D5 each
independently measure `skipped` (never the claimed `pass`), D2/D3 stay honestly `pass`.
Updated 4 existing tests that assumed a since-retired reachable "genuine all-pass, rc=0"
path (`test_all_pass_fixture_writes_complete_receipt` → renamed
`test_uncorroborated_all_pass_self_report_never_reaches_complete`, now asserting
`verdict: incomplete` + D1/D4/D5 `skipped` + D2/D3/D6 `pass` + a still-valid hash-chain;
the 3 chain-tamper tests no longer assert an initial `rc == 0` — they instead assert the
freshly-written receipt is internally self-consistent via `ceg.verify_receipt(...) == []`
before tampering it). No other existing test needed a change (the parametrized
single-dimension / D2/D3-forge / empty-delivery / GATE-3-forge tests only assert
`rc != 0` + `verdict: incomplete`, both still true).

**Verify (STAGED, `git add -A` first):**
- `python3 -m pytest tests/test_check_evidence_gate.py tests/test_ws_g_proof_delivery.py tests/test_ws_g_delivery_scorecard.py -q`
  → **72 passed** (22 + 16 + 34; both the new fabricated-fixture forge test and the prior
  no-artifact GATE-3 forge test pass; the `test_ws_g_proof_delivery.py` /
  `test_ws_g_delivery_scorecard.py` acceptance suites — files I did NOT touch — pass
  unmodified, since neither asserts a `"pass"` verdict for D1/D4/D5 via
  `check_evidence_gate.py`, only `"fail"`/`"skipped"`, both unaffected by this fix).
- `python3 -m pytest -q` (full) → **2299 passed, 4 skipped, 0 xfailed** (was 2298/4/0
  before this fix; +1 net new test).
- `python3 scripts/diagnostics.py` → **100/100**.
- `python3 scripts/check_attestation.py` → exit 0.
- `python3 scripts/board_lint.py` → exit 0 (180 tickets; 1 pre-existing non-fatal WARN on
  DAS-1507, unrelated).
- `ruff check scripts/check_evidence_gate.py tests/test_check_evidence_gate.py` → clean.
- `grep -n "/Users/owner\|/home/"` over both touched files → no hits.
- `git status --short metrics/` — no changes; no `.delivery.json` committed to tracked
  `metrics/`.

**Footprint (per the dispatch's hard file-scope constraint):** only
`scripts/check_evidence_gate.py`, `tests/test_check_evidence_gate.py`, and this ticket +
DAS-1594's ticket file were touched this run. `scripts/agent_eval.py`, `evals/`,
`scripts/wave_runner.py`, `tests/test_ws_g_proof_delivery.py`,
`tests/test_ws_g_delivery_scorecard.py`, and every other ticket were NOT modified.

**Disposition:** the DEEPER GATE-4 false-green hole (DAS-1594's routed finding) is
CLOSED — both the prior "no artifacts at all" forge and the new "plausible-but-unattested
artifacts" forge are dead. `status: in_review`, `assignee` → `cto` (re-routing for
re-review of the reopened gate per "never review your own work" — NOT self-closing back
to `done`).

⛔ **LOCAL-ONLY constraint honored**: no git branch/commit/push/PR/remote created this
run.

### 2026-07-24 — CTO (GATE-3 re-closure — architectural adjudication, DECISION A: ACCEPT fail-closed)
**Adjudicated the fail-closed trade-off (RACI 3.1/3.6) and re-closed GATE-3 for WS-G. This
ticket → `done`.** The red-team + two deliverer fixes exposed and killed BOTH forges in the
"no-false-green" evidence gate; the residual is that `verdict: complete` is now UNREACHABLE
via this gate until a follow-up attests D1/D4/D5 into the tamper-evident chain. I judge that
residual ACCEPTABLE now and CLOSE the gate. Cleaned a stray `</content>` artifact left at the
file tail while appending.

**Both forges CONFIRMED DEAD — read `scripts/check_evidence_gate.py` end-to-end, verified live:**
- **Forge 1 (trust the scorecard's self-reported status)** — dead. `corroborate()` never
  reads the caller's `status` as authoritative for ANY of the six dimensions; it REPLACES
  D1/D4/D5/D6 with the independently measured status (line ~324) and re-derives D2/D3 from the
  committed wave-attestation + evidence store. A self-report/measurement disagreement is itself
  appended to `errors`, which alone forces FAIL.
- **Forge 2 (trust deliverer-authored `fixtures/{diagnostics.json,stage-board.md,golden-eval.json}`
  for D1/D4/D5)** — dead. `measured_dimensions()` downgrades a measured `pass` to `skipped` for
  `_UNCORROBORATED_CLAIM_DIMENSIONS = (aadl_gates_closed, diagnostics_100, golden_eval)` — a
  plausible, internally-consistent, self-authored `fixtures/` artifact can never alone earn
  green (no tamper-evident anchor records those three facts yet). A measured `fail` (an open
  gate, diagnostics < 100) is NOT downgraded and passes through — detecting a self-evident lie
  needs no corroboration, only trusting a claimed truth does. D6 `anti_gaming_probe` stays
  authoritative (EXECUTION-verified via `agent_eval.mutation_probe` — real code run, not a file
  claim); D2/D3 stay store-corroborated.
- `verdict_of` is conjunctive (SKIP ≠ pass), so with D1/D4/D5 capped at `skipped`/`fail`,
  `complete` is genuinely unreachable via this gate. That is the intended fail-closed state.

**Why ACCEPT (Decision A over B) — the architecture call:**
1. **The crux property is fully satisfied.** ADR-0037 §Enforcement(a) "no false-green" is the
   whole point of ED-1; this gate can reject EVERY forgery (self-report, no-artifact,
   plausible-but-unattested-fixture, forged count, tampered chain) and only cannot yet ACCEPT a
   true delivery. A gate that rejects all lies but defers accepting a truth — pending a
   documented follow-up — is exactly ADR-0020's "honest empty over silent green." Honest-unable
   beats false-able.
2. **Nothing needs to certify `complete` today.** `ws_g_proof` is OFF by default (flag-off is
   byte-identical/inert). The real 0→100 proof run + deploy (DAS-1595) are independently
   infra-gated — `blocked` absent a provisioned tenant VM + Founder go-ahead — so no live path
   currently depends on reaching `complete` through this gate. Requiring the fuller
   attestation-chain change NOW (Option B: a `wave_runner.py`/`snapshot_evidence.py` schema
   extension) would block GATE-3 on infra-track work that the deploy ticket already owns and is
   itself gated on — no correctness gain today, only serialization cost.
3. **The follow-up is genuinely part of the real-proof deploy.** Extending the attested chain
   to record the diagnostics score / AADL gate-closure state / golden-eval result belongs with
   the first real receipt DAS-1595 writes — so I bind it there as a MUST-DO blocking condition
   (below) rather than leaving it implicit.

**True-green follow-up BOUND to DAS-1595** (appended a `## Blocking conditions (GATE-3 residual —
CTO, DAS-1592)` section to `board/tickets/DAS-1595-ws-g-deploy-proof-tenant-vm.md`): before a
real 0→100 delivery can certify `verdict: complete`, the wave attestation / `snapshot_evidence`
must be extended to record + attest the diagnostics score, AADL gate-closure state, and
golden-eval result, and `check_evidence_gate` must corroborate D1/D4/D5 against that
tamper-evident anchor (Option A) — the gate is intentionally fail-closed until then.

**Independently verified (STAGED, `git add -A` first):**
- `pytest tests/test_check_evidence_gate.py tests/test_ws_g_proof_delivery.py -q` → **38 passed**
  (both forges rejected: the no-artifact GATE-3 forge and the plausible-fixture GATE-4 forge).
- `pytest -q` (full) → **2299 passed, 4 skipped, 0 xfailed**.
- `scripts/diagnostics.py` → **100/100**; `scripts/check_attestation.py` → exit 0;
  `scripts/board_lint.py` → exit 0 (180 tickets; only the pre-existing DAS-1507 WARN, unrelated).
- Read the module's TRUST BOUNDARY docstring + `measured_dimensions()`/`corroborate()` — the
  fail-closed downgrade is real, not cosmetic.

**Scope honored:** edited ONLY this ticket + DAS-1595's ticket file (the binding). Did NOT touch
`scripts/check_evidence_gate.py` or any impl. **LOCAL-ONLY**: no git branch/commit/push/PR/remote.

**Consequence:** GATE-3 (Development) CLOSED for WS-G on verified-local-green. AC "Merged PR,
green CI" stays honestly unchecked — branch + PR materialization from this working tree is the
one residual, owned by Backend EM / orchestrator, NOT a re-open of the dev gate. This UNBLOCKS
DAS-1594's GATE-4 (qa-lead): the fabricated-fixture negative (SC-004) now genuinely rejects.
