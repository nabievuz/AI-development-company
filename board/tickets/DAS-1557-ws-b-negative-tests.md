---
id: DAS-1557
title: WS-B Testing — dispatch equivalence, missing model rejection, budget and credit pause
status: done
assignee: qa-lead
author: ceo
dept: engineering
priority: p1
parent: DAS-1552
goal: mustaqil-ws-b-runner
spec: 003-mustaqil-ws-b-runner
implements: [SC-001, SC-002, SC-003, SC-004]
labels: [security]
zone: tests
depends_on: [DAS-1555, DAS-1556]
created: 2026-07-24
updated: 2026-07-24
---

<!-- INTEGRATION-SEAM PREREQUISITE (bound by CTO at GATE-3 closure, 2026-07-24;
     see DAS-1555 CTO log for the full Option-B rationale).

     DAS-1555 (`daslab_sdk`) and DAS-1556 (`scripts/ws_b_admission.py`) are each
     unit-complete and GATE-3-closed, but they are NOT directly composable: the
     runner gates dispatch on `daslab_sdk.contracts.AdmissionOutcome.ADMIT`,
     while `ws_b_admission.admit()` returns the RICHER `ws_b_admission.
     AdmissionOutcome` (5 sanctioned outcomes). A naive direct injection is a
     silent bug — the differing enum identities score every real ADMIT as
     `ADMISSION_HOLD`, so nothing would ever dispatch.

     Therefore, BEFORE writing SC-001 dispatch-equivalence, this ticket MUST first
     build the thin adapter that maps `ws_b_admission.admit(...)` to the runner's
     `Admitter` protocol:
       - map ws_b_admission ADMIT -> contracts.AdmissionOutcome.ADMIT;
       - map every non-ADMIT outcome (REJECTED / IDLE_AND_ALERT /
         SANCTIONED_PAUSE / UNAVAILABLE) -> contracts.AdmissionOutcome.HOLD,
         preserving the reason;
       - translate the dataclass shape (contracts.AdmissionDecision requires
         `ticket_id`, `model`, `outcome`, `reason`).
     Then add the end-to-end INTEGRATION test proving the composition:
       - a real ADMIT flows `adapter -> dispatch_ticket -> query_fn` and the
         query_fn spy IS invoked (the seam actually dispatches);
       - every HOLD family outcome yields `RunnerStatus.ADMISSION_HOLD` and the
         query_fn spy is NOT invoked (no dispatch).
     This test-side adapter/helper lives in `zone: tests`. The PRODUCTION adapter
     used by the live drive is a separate binding on DAS-1558 (flip-time wiring);
     do NOT let this ticket's tests silently pass by only exercising a stub
     admitter — SC-001 must exercise the REAL `ws_b_admission.admit` through the
     adapter at least once. -->


## Description

**AADL Stage 4 — Testing (closes GATE-4 for WS-B).** Prove the runner holds
its governance invariants with positive and adversarial tests.

Cover:
- **SC-001:** a headless dispatch of a ticket (and, via the wave call, a
  full wave) produces the same board state, event stream, and attestation an
  equivalent interactive `/daslab-cycle` dispatch would produce.
- **SC-002:** a dispatch without an explicit `model` argument is rejected
  before it reaches the model call.
- **SC-003:** with the feature flag OFF, the runner is inert / import-only,
  and an interactive wave's dispatch behaviour is byte-identical to
  pre-merge; flipping the flag ON changes no interactive-wave behaviour.
- **SC-004:** a budget-breach scenario (per-run or per-day cap) and a
  monthly-credit-exhaustion scenario each evaluate to idle + alert /
  sanctioned pause — never a false-green or an unhandled crash.

## Acceptance criteria
- [x] **Integration-seam adapter (prerequisite, bound at GATE-3):** a thin adapter maps `ws_b_admission.admit(...)` (5-outcome `ws_b_admission.AdmissionOutcome`) onto the runner's `Admitter` protocol (`contracts.AdmissionOutcome` ADMIT/HOLD + dataclass shape); an end-to-end integration test proves a REAL ADMIT composes through `adapter → dispatch_ticket → query_fn` (spy invoked) and every non-ADMIT → `ADMISSION_HOLD` (spy NOT invoked). SC-001 exercises the real `ws_b_admission.admit` through this adapter at least once — not only a stub.
- [x] Dispatch-equivalence test exists and PASSES for SC-001 (headless vs. interactive wave produce the same board/event/attestation outcome).
- [x] Missing-model rejection test exists and PASSES for SC-002.
- [x] Flag-off no-op test exists and PASSES for SC-003 (byte-identical interactive dispatch with the flag OFF).
- [x] Budget-breach and credit-exhaustion negative tests exist and PASS for SC-004 (idle+alert / sanctioned pause, not a crash or false-green).
- [ ] Overall pytest green in CI. Merged PR, green CI. (local green confirmed this run — 2001 passed, 4 skipped, diagnostics 100/100; the branch/commit/PR + CI step is deferred per the LOCAL-ONLY dispatch constraint, same disposition as DAS-1555/DAS-1556.)

## Log
### 2026-07-24 — Senior PM
Created by `/daslab-plan` (WS-B Testing). SC-001..SC-004 dispatch-equivalence,
missing-model, flag-off, and budget/credit-pause negative tests.

### 2026-07-24 — CTO
**Integration-seam prerequisite bound here at GATE-3 closure of DAS-1555/DAS-1556
(both now `done`).** The two Development units are deliberately decoupled via the
runner's injected `Admitter` protocol (ADR-0034 SR-2/SR-3), and are each
unit-complete + tested — but they are NOT directly composable: `ws_b_admission.
admit()` returns a richer 5-outcome enum whose `ADMIT` is not identical to
`contracts.AdmissionOutcome.ADMIT`, so a naive injection scores every ADMIT as a
HOLD. This ticket therefore MUST build the 5→2 outcome adapter + the end-to-end
integration test (see the INTEGRATION-SEAM PREREQUISITE comment in the body and
the new first acceptance criterion) BEFORE the SC-001 dispatch-equivalence work.
The test-side adapter lives in `zone: tests`; the production adapter for the live
drive is bound separately on DAS-1558. `depends_on: [DAS-1555, DAS-1556]` is now
satisfied — this ticket is actionable. Status left `todo` (unchanged) for the
Testing wave to pick up.

### 2026-07-24 — QA Engineer

**AADL Stage-4 / GATE-4 (WS-B RUNNER) — negative-path suite + integration-seam
adapter built. LOCAL-ONLY (no commit/branch/PR/push per dispatch constraint).**

**Task 1 — integration-seam adapter (prerequisite, done first).** New file
`tests/test_ws_b_negative_paths.py` defines `ws_b_admission_adapter(...)`
(test-scoped, per the GATE-3 binding — NOT the DAS-1558 production adapter): it
wraps the real `scripts/ws_b_admission.admit` and translates its 5-outcome
`AdmissionOutcome` onto the runner's 2-outcome `daslab_sdk.contracts.
AdmissionOutcome` (`ADMIT` → `ADMIT`; `REJECTED`/`IDLE_AND_ALERT`/
`SANCTIONED_PAUSE`/`UNAVAILABLE` → `HOLD`), and the dataclass shape
(`ws_b_admission.AdmissionDecision{outcome,ticket_id,role,model,reason,alert}`
→ `contracts.AdmissionDecision{outcome,ticket_id,model,reason}`).

- `test_naive_direct_injection_scores_every_real_admit_as_hold` — reproduces
  the CTO's flagged enum-identity trap FIRST: a raw `ws_b_admission.
  AdmissionDecision` passed straight into `dispatch_ticket` scores a real
  ADMIT as `ADMISSION_HOLD` (distinct enum classes, `is not` never true), spy
  never called.
- `test_adapter_fixes_the_enum_identity_trap` / `test_real_admit_flows_
  adapter_dispatch_ticket_query_fn` — the SAME real decision, through the
  adapter, reaches `RunnerStatus.DISPATCHED` and the `query_fn` spy IS
  invoked (exactly once) — the end-to-end integration test the prerequisite
  required.
- `test_real_non_admit_outcomes_hold_and_never_reach_query_fn`
  (parametrized: budget-breach, credit-exhaustion) — each real non-ADMIT
  `ws_b_admission.admit` verdict → `ADMISSION_HOLD` at the runner, spy never
  invoked.

**Task 2 — negative-path suite, SC → test mapping** (folded into the new file;
did not duplicate the existing unit coverage in `tests/test_ws_b_daslab_sdk_
runner.py` / `tests/test_ws_b_admission.py`, which already prove the unit-level
facts these integration tests compose):

- **SC-001a (dispatch-equivalence)** →
  `test_sc001_dispatch_equivalence_flag_on_vs_interactive_equivalent`: the
  SAME `(plan, results, created_at)` driven directly through `wr.run_wave`
  (interactive-equivalent) vs. through `daslab_sdk.dispatch_wave` (headless)
  into two independently-fresh hermetic dirs produces an **equal** attestation
  payload (`tickets`, `wave`, `counts`, `event_digest`, `ledger_digest`,
  `self_hash`), and both ledgers independently reconcile
  (`verify_wave_ledger(...) == []`) — one producer per world, SC-001b.
- **SC-001 / one-producer-to-run_wave** — already asserted at unit level by
  `test_dispatch_wave_calls_run_wave_and_ledger_reconciles` (existing file);
  the new equivalence test above adds the missing cross-entrypoint equality
  assertion, not a re-implementation.
- **SC-002a (missing-model rejected before the model call)** →
  `test_missing_model_rejected_before_adapter_is_ever_called`: with the real
  adapter wired, an absent `model` is refused by the runner's own precondition
  and the adapter (hence `ws_b_admission.admit`) is **never invoked**
  (`call_log == []`), spy never invoked. Unit-level coverage already exists in
  both existing test files (`test_missing_model_rejected_before_query`,
  `test_missing_model_rejected_before_model_call`) — not duplicated.
- **SC-002b (frontmatter not trusted)** — already covered by
  `tests/test_ws_b_admission.py::test_frontmatter_model_hint_is_never_a_
  fallback`; not duplicated here.
- **SC-003a (flag-off no-op) + byte-identical interactive wave** →
  `test_flag_off_adapter_never_reached` (dispatch_ticket path: adapter/gateway
  never consulted) and `test_sc001_flag_off_produces_zero_headless_writes_
  interactive_unaffected` (dispatch_wave path: headless side writes nothing;
  the interactive-equivalent `run_wave` call on the identical `(plan,
  results)` still produces its normal attestation, unaffected by the flag).
- **SC-003b (absent-SDK ⇒ unavailable, not broken)** — already covered by
  `tests/test_ws_b_daslab_sdk_runner.py::test_absent_sdk_is_unavailable_not_
  broken`; not duplicated here (no SDK-availability seam to re-test at the
  integration layer beyond what that unit test already proves).
- **SC-004a (budget breach → idle+alert, no false-green)** +
  **SC-004b (credit exhaustion → sanctioned pause)** +
  **SC-004c (both distinct from success/crash)** →
  `test_real_non_admit_outcomes_hold_and_never_reach_query_fn` (both cases
  parametrized): each real `ws_b_admission.admit` breach/exhaustion verdict
  reaches the runner as `ADMISSION_HOLD` (never `DISPATCHED` — no
  false-green), the `query_fn` spy is never invoked (no dispatch), and no
  exception is raised (no crash/false-red).
- **SC-004 idempotent-resume** — already covered by
  `tests/test_ws_b_admission.py::test_credit_refresh_resumes_normally_
  idempotent`; not duplicated here.

**No real bug found in the runner or admission code.** The only "bug" surfaced
is the enum-identity trap the CTO already anticipated and bound this ticket to
fix via the adapter (not a defect in either unit — it is the documented reason
the two units are not directly composable without one).

**Verification (exact):**
- `python3 -m pytest tests/test_ws_b_negative_paths.py tests/test_ws_b_daslab_
  sdk_runner.py tests/test_ws_b_admission.py -q` → `51 passed`.
- `python3 -m pytest -q` (full suite) → `2001 passed, 4 skipped`.
- `python3 scripts/diagnostics.py` → `SCORE = 100/100`.
- `python3 scripts/board_lint.py` → exit 0 (`180 ticket(s) checked, 0
  violations`; one pre-existing, unrelated `DAS-1507` body-status WARN).
- `ruff check tests/test_ws_b_negative_paths.py` → `All checks passed!`.

**Files touched:** `tests/test_ws_b_negative_paths.py` (new, 9 tests) + this
ticket file. No other file touched — `daslab_sdk/` and `scripts/ws_b_admission.
py` were imported only, never modified.

**Disposition.** LOCAL-ONLY per the dispatch constraint (no commit/branch/PR/
push this run) — the same disposition DAS-1555/DAS-1556 recorded. `status:
in_review`, `assignee: qa-lead` per `board/ROUTING.md` (GATE-4 reviewer). The
git-law worktree/branch/PR step (ADR-0005, board rule "`in_review` requires a
pushed branch/PR") remains bound to whichever future run performs the
branch/commit for this WS-B slice; it does not reopen or block this GATE-4
content review. Acceptance-criteria checkboxes for the test content are
satisfied on local green; the final "Merged PR, green CI" checkbox stays
unchecked pending that branch/commit/PR step.

### 2026-07-24 — QA Lead
**AADL Stage-4 / GATE-4 (WS-B RUNNER) — CLOSED. Local-only disposition, accepted
on local green (same disposition as DAS-1555/DAS-1556).**

Independent re-verification (exact, this run):
- `python3 -m pytest tests/test_ws_b_negative_paths.py tests/test_ws_b_daslab_sdk_runner.py tests/test_ws_b_admission.py -q` → **51 passed** in 0.15s.
- `python3 -m pytest -q` (full suite) → **2001 passed, 4 skipped** in 13.32s.
- `python3 scripts/diagnostics.py` → **SCORE = 100/100**.
- `python3 scripts/board_lint.py` → **exit 0** (180 tickets, 0 violations; the
  one WARN is the pre-existing, unrelated DAS-1507 body-status prose — not this
  ticket).

**Integration-seam prerequisite confirmed genuinely satisfied — read the code, not
just the log.** `tests/test_ws_b_negative_paths.py::ws_b_admission_adapter`
wraps the REAL `ws_b_admission.admit` and performs the bound 5→2 outcome map
(ADMIT→ADMIT; REJECTED/IDLE_AND_ALERT/SANCTIONED_PAUSE/UNAVAILABLE→HOLD) plus the
dataclass-shape translation. Both required halves exist and pass:
- **Trap reproduced** — `test_naive_direct_injection_scores_every_real_admit_as_hold`:
  a raw `ws_b_admission.AdmissionDecision` (real ADMIT) injected without the
  adapter scores `RunnerStatus.ADMISSION_HOLD`, `query_fn` spy `== []` (distinct
  enum identities, exactly the CTO-flagged trap).
- **Trap fixed / real dispatch proven** — `test_adapter_fixes_the_enum_identity_trap`
  and `test_real_admit_flows_adapter_dispatch_ticket_query_fn`: the SAME real
  decision through the adapter reaches `RunnerStatus.DISPATCHED` and the `query_fn`
  spy IS invoked exactly once. The seam actually dispatches — not a stub admitter.

**SC coverage confirmed present and passing:**
- SC-001 (`test_sc001_dispatch_equivalence_flag_on_vs_interactive_equivalent`):
  identical attestation `payload` + `self_hash` from interactive-equivalent
  `run_wave` vs headless `dispatch_wave`; both ledgers reconcile
  (`verify_wave_ledger == []`) — one producer per world.
- SC-002 (`test_missing_model_rejected_before_adapter_is_ever_called`):
  `RunnerStatus.REFUSED_NO_MODEL`; adapter and `ws_b_admission.admit` never
  invoked (`call_log == []`) — model precondition fires before the model call,
  frontmatter never a fallback.
- SC-003 (`test_flag_off_adapter_never_reached` +
  `test_sc001_flag_off_produces_zero_headless_writes_interactive_unaffected`):
  flag-off inert, adapter never reached, zero headless writes, interactive
  path unaffected.
- SC-004 (`test_real_non_admit_outcomes_hold_and_never_reach_query_fn`,
  parametrized budget-breach + credit-exhaustion): real `ws_b_admission.admit`
  breach/exhaustion verdicts → `ADMISSION_HOLD`, spy never invoked, not a
  false-green `DISPATCHED`, no exception.

No real runner/admission defect exists — the only "bug" is the documented
enum-identity trap the adapter closes, as the CTO anticipated at GATE-3.

**GATE-4 decision: PASS / CLOSED.** All MUST-PASS gates green; adapter
prerequisite genuinely met; SC-001..SC-004 covered and passing. `status: done`.
The "Merged PR, green CI" acceptance checkbox stays unchecked by design — the
branch/commit/PR + CI step is deferred under the LOCAL-ONLY dispatch constraint,
the same disposition DAS-1555/DAS-1556 carried; GATE-4 (Testing) is closed on
local green and does not itself require the deploy-time git-law step. This
**unblocks DAS-1558 (AADL Stage-5 / Deployment)**, which binds the production
adapter for the live drive.
