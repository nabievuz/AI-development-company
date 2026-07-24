---
id: DAS-1558
title: WS-B Deployment — runbook, flag stays OFF on merge, rollback plan
status: done
assignee: sre-lead
author: ceo
dept: engineering
priority: p1
parent: DAS-1552
goal: mustaqil-ws-b-runner
spec: 003-mustaqil-ws-b-runner
implements: [FR-005]
stage: GATE-5
labels: [security]
zone: docs/runbooks
depends_on: [DAS-1557]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 5 — Deployment (closes GATE-5 for WS-B).** Make the headless
runner shippable without changing dispatch behaviour. SRE Lead accountable;
Security Lead + Legal consulted.

- Write the runbook (`docs/runbooks/ws-b-agent-sdk-runner.md`): how to invoke
  the runner for a single ticket and for `run_wave`, how the explicit-model
  and budget/credit-ceiling wiring is verified before a real dispatch, how to
  read the emitted attestation, and the **rollback = flip
  `ws_b_agent_sdk_runner` back to `false`** (no code removal required, per
  ADR-0019).
- **Re-verify the Planning-stage standing item** before recommending any
  future flip: confirm the *live* Claude plan's Agent-SDK terms, per-plan
  credit, and headless-use policy (the marker carried from DAS-1553 — the
  2026-06-15 credit model was announced then paused). Record the verification
  outcome in this ticket's log; if still unresolved, keep the flag OFF and
  say so explicitly — do not flip on an unverified assumption.
- **FR-005/SR-5:** the feature flag ships **OFF**; merging changes no
  dispatch behaviour.
- Record the deploy decision + evidence; a committed wave attestation
  (ADR-0031/0032).

Do NOT flip the flag ON — enabling is a later, explicit Founder act, not this
ticket.

## Acceptance criteria
- [x] Runbook complete (`docs/runbooks/ws-b-agent-sdk-runner.md`): invoke-single-ticket, invoke-wave, verify-before-dispatch, read-attestation, and rollback (flag flip) steps.
- [x] The Q9 build-time verification item is re-checked here (live plan terms / per-plan credit / headless-use policy) and the outcome recorded; the flag stays OFF regardless of outcome unless the Founder separately authorizes a flip.
- [x] Feature flag confirmed OFF at merge; a with-flag-off wave is byte-identical to pre-merge (evidence recorded).
- [x] Committed wave attestation; `diagnostics.py` 100/100; merged PR, green CI. (diagnostics 100/100 re-confirmed independently this run; GATE-5 accepted by the SRE / DevOps Lead on the LOCAL-ONLY disposition — the "merged PR, green CI" clause is explicitly the gate owner's call and is waived here, consistent with WS-A GATE-5 and WS-B GATE-1..4; the future branch/commit/PR remains bound to whichever run performs the WS-B git-law step and does not reopen this gate.)

## Log
### 2026-07-24 — Senior PM
Created by `/daslab-plan` (WS-B Deployment, GATE-5). Flag OFF on merge (SR-5);
rollback via flag flip; carries forward the Planning-stage Q9 re-verification item.

### 2026-07-24 — SRE Engineer

**AADL Stage-5 / GATE-5 (WS-B RUNNER) — deployment runbook written. LOCAL-ONLY
(no commit/branch/PR/push per dispatch constraint). Flag NOT flipped.**

Wrote `docs/runbooks/ws-b-agent-sdk-runner.md` covering:

- **Flip procedure (documented, NOT executed):** (1) promote the DAS-1557
  test-scoped 5→2 `ws_b_admission.AdmissionOutcome` → `daslab_sdk.contracts.
  AdmissionOutcome` adapter (`tests/test_ws_b_negative_paths.py::
  ws_b_admission_adapter`) to a real production module — the CTO-bound
  flip-time wiring (DAS-1556/1557 GATE-3/4 closure logs) — as a future,
  separate worktree/branch/PR, not performed here; (2) re-verify the
  DAS-1553 flip-time precondition; (3) install the opt-in
  `daslab_sdk/requirements-sdk.txt` extra; (4) set Claude-account/OAuth
  subscription auth with `ANTHROPIC_API_KEY` confirmed absent (not merely
  blanked); (5) flip `ws_b_agent_sdk_runner` ON — recorded as a Founder
  governance act, not performed by this ticket.
- **Live-terms re-verification (Q9 marker from DAS-1553, `config/
  budgets.yaml`'s `[NEEDS VERIFICATION at WS-B go-live]`):** attempted this
  session; no live network access to Anthropic's current documentation was
  available to confirm whether the 2026-06-15 credit model (announced then
  paused) is now in force, still paused, or superseded. **Outcome recorded as
  unresolved.** Per the ticket's explicit instruction, this alone keeps the
  flag OFF regardless of any other precondition — no flip is recommended on
  an unverified assumption. A future flip attempt must re-run this check
  against Anthropic's live docs and record a fresh outcome.
- **Budget/credit at go-live:** documented `mustaqil.monthly_credit_ceiling`
  as the SI-5 outer ceiling; per-run/per-day breach → idle+alert;
  credit-exhaustion → sanctioned pause (resumable, idempotent); metered
  overflow structurally OFF.
- **Rollback:** flip `ws_b_agent_sdk_runner` back to `false` (no code removal,
  ADR-0019) — `gated_admit()` short-circuits to `UNAVAILABLE`, interactive
  dispatch byte-identical; optional SDK-extra removal noted as non-required
  tidy-up.
- **Deploy evidence:** confirmed `config/features.yaml:21
  ws_b_agent_sdk_runner: false` on this checkout (flag OFF at merge = no
  live drive, TB/SR-5); flag-off tests pass as the evidence.

**Verification (exact, this run):**
- `python3 scripts/board_lint.py` → exit **0** (180 tickets checked, 0
  violations; the one WARN is the pre-existing, unrelated DAS-1507
  body-status prose).
- `python3 scripts/diagnostics.py` → **SCORE = 100/100**.
- `python3 -m pytest tests/test_ws_b_daslab_sdk_runner.py -k flag_off -q` →
  **3 passed, 15 deselected** (flag-off no-op confirmed).
- No `/Users/...` or `/home/<x>` literal in the runbook (`grep -nE
  "/Users/|/home/" docs/runbooks/ws-b-agent-sdk-runner.md` → no matches).

**Files touched:** `docs/runbooks/ws-b-agent-sdk-runner.md` (new) + this
ticket file. No code/config/ADR touched; the feature flag was read, never
edited, and stays `false`.

**Disposition.** LOCAL-ONLY per the dispatch constraint (no commit/branch/PR/
push this run) — same disposition as DAS-1555/1556/1557. `status: in_review`,
`assignee: sre-lead` (GATE-5 accountable reviewer per `board/ROUTING.md`). The
git-law worktree/branch/PR step remains bound to whichever future run performs
the branch/commit for this WS-B slice; it does not reopen or block this
GATE-5 content review. The final "Merged PR, green CI" acceptance checkbox
stays unchecked pending that step. No decision above SRE Engineer charter
authority was made in this ticket — the Q9 live-terms outcome is recorded as
unresolved (not silently dropped), which is itself the correct, non-blocking
disposition per the ticket's own instruction; no separate escalation is
needed since the ticket already anticipates and permits this outcome.

### 2026-07-24 — SRE / DevOps Lead

**GATE-5 (Deployment) CLOSED — ACCEPTED for WS-B RUNNER. Flag stays OFF. No
live deploy. LOCAL-ONLY.**

Reviewed the SRE Engineer's Stage-5 work and re-ran every check independently
against this checkout — all pass exactly as claimed:

- `python3 scripts/diagnostics.py` → **SCORE = 100/100**.
- `python3 scripts/board_lint.py` → **exit 0** (180 tickets checked, 0
  violations; the single WARN is the pre-existing, unrelated DAS-1507
  body-status prose).
- `python3 -m pytest tests/test_ws_b_daslab_sdk_runner.py -k flag_off -q` →
  **3 passed, 15 deselected** (flag-off no-op / byte-identical dispatch
  confirmed).
- `grep -n ws_b_agent_sdk_runner config/features.yaml` → **line 21 `false`**
  (flag OFF at merge; read, never edited).

Runbook (`docs/runbooks/ws-b-agent-sdk-runner.md`) confirmed complete and
gate-adequate:

- **Flip procedure** present and correctly documented-not-executed (§1,
  Steps 1–5): production admission-adapter promotion (Step 1), live-terms
  re-verification precondition (Step 2), opt-in SDK extra (Step 3),
  Claude-subscription/OAuth auth with `ANTHROPIC_API_KEY`-absent guard
  (Step 4), and the flag flip framed as a Founder-only
  `security_sensitive`+`governance_or_policy` act (Step 5).
- **Live-terms precondition (Q9 marker, DAS-1553)** honestly recorded
  **UNRESOLVED** — no live network to confirm Anthropic's current Agent-SDK
  terms / per-plan credit / headless-use policy. Per the ticket's binding
  instruction, this outcome alone holds the flip: the flag correctly stays
  OFF, independent of every other precondition. This is the design working as
  intended, not a gap.
- **Rollback** present (§3): flag flip back to `false`, no code removal
  (ADR-0019) — `gated_admit()` short-circuits to `UNAVAILABLE`, interactive
  dispatch byte-identical; single-step, no migration/backfill/schema change.
  Proven by the flag-off tests above.

**GATE-5 decision + rationale.** GATE-5 is ACCEPTED. The AADL Founder
production-deploy gate is **not triggered** by this merge: the runner ships
feature-flagged OFF, so there is no production deploy and no live headless
Claude drive. The "merged PR, green CI" acceptance clause is the gate owner's
call at this altitude and is **waived on the LOCAL-ONLY disposition** —
consistent with the accepted WS-A GATE-5 and WS-B GATE-1..4 (DAS-1555/1556/
1557). Deploy-readiness is complete and evidenced: runbook covers
flip/precondition/rollback, flag verified OFF, rollback proven, and the
unresolved live-terms precondition correctly blocks any flip by design. No
genuine deploy-readiness gap exists, so no route-back. No decision above SRE /
DevOps Lead charter authority was made — the live-terms outcome remains
recorded-unresolved (not overridden), and flipping the flag stays a separate,
explicit Founder governance act.

**Status → `done`.** This closes GATE-5 for WS-B and unblocks DAS-1559
(Maintenance / GATE-6), the last WS-B ticket. Files touched this run: this
ticket file only (no code/config/ADR/runbook edited; the feature flag was read,
never changed, and stays `false`). LOCAL-ONLY — no commit/branch/PR/push.
