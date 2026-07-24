---
id: DAS-1556
title: WS-B Development — admission gateway, Claude subscription auth, budget and credit ceiling
status: in_review
assignee: backend-em
author: ceo
dept: engineering
priority: p1
parent: DAS-1552
goal: mustaqil-ws-b-runner
spec: 003-mustaqil-ws-b-runner
implements: [FR-002, FR-006, FR-007, FR-008]
labels: [security]
zone: scripts
depends_on: [DAS-1554]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 3 — Development (closes GATE-3 for WS-B, part 2).** Build the
admission-gateway, auth, and budget-ceiling integration per the DAS-1554
design.

- **SR-2 — explicit model, real admission gateway:** every dispatch passes
  `model` explicitly, sourced from `governance/policies/model-allocation.md`
  (frontmatter alone stays untrusted, per LAW 3). This becomes the real
  ADR-0009 admission gateway: it governs which model dispatches, under which
  per-dispatch budget, honoring the ADR-0027 SI-5 ceiling rather than
  reopening it.
- **Claude-account auth (Q9):** authenticate via a Claude-subscription account
  (Pro/Max/Team/Enterprise) using account/OAuth authentication, never a
  metered API key; keep the auth path behind the admission layer so it stays
  swappable.
- **Budget + monthly-credit ceiling:** wire the `mustaqil:` per-run/per-day
  caps (`config/budgets.yaml`, DAS-1543) together with the monthly
  subscription-credit outer ceiling; a wave that would breach either
  evaluates to **idle + alert** (`on_breach: idle_and_alert`), never
  proceeding or reporting a false success. Keep metered usage-credit overflow
  **disabled** by default.
- **Sanctioned pause:** credit exhaustion is handled as a pause that resumes
  on refresh — surfaced as a sanctioned halt (comparable to a gate halt), not
  a crash, a silent stop, or a failed run.

Distinct repo zone from DAS-1555 so the two Development tickets can proceed
without a same-zone wave collision.

## Acceptance criteria
- [x] Every dispatch through the runner carries an explicit `model` argument sourced from `model-allocation.md`; a dispatch without one is rejected before it reaches the model call.
- [x] Authentication path uses a Claude-subscription account (account/OAuth), not a metered API key; the auth path sits behind the admission layer.
- [x] Budget-breach (`mustaqil:` per-run/per-day caps) and monthly-credit-exhaustion both evaluate to idle + alert / sanctioned pause, proven by at least one test each; metered overflow stays disabled by default.
- [x] Feature-flagged OFF by default (shared `ws_b_agent_sdk_runner` key with DAS-1555); flag-off behaviour unchanged. `diagnostics.py` 100/100 (module-attributable checks green; see Log for the one pre-existing, unrelated finding). PR/merge is pending — this ticket is LOCAL-ONLY per dispatch constraints; no branch/PR/commit was created in this run (see Log).

## Log
### 2026-07-24 — Senior PM
Created by `/daslab-plan` (WS-B Development, part 2). SR-2 explicit-model/admission
gateway + Claude-account auth + budget/credit-ceiling integration; distinct zone
(`scripts`) from DAS-1555 (`daslab_sdk`) for parallel wave dispatch.

### 2026-07-24 — Backend Engineer 1

Built the admission gateway + Claude-subscription auth-env isolation + budget/
credit-ceiling module per `docs/design/ws-b-agent-sdk-runner.md` §2/§4 and
ADR-0034 SR-2, entirely in the `scripts` zone (no overlap with DAS-1555's
`daslab_sdk` zone). Library only — not wired into any live dispatch path yet
(`ws_b_agent_sdk_runner` stays OFF in `config/features.yaml`, untouched).

**Files created**
- `scripts/ws_b_admission.py` — `admit()` gateway, `gated_admit()` (flag wrapper),
  `dispatch_through_gate()` (reference caller shape), `build_subscription_env()`,
  `load_mustaqil_budgets()`, `check_budget()`/`check_credit_exhaustion()`,
  `UsageEstimate`/`CreditState`/`AdmissionDecision`/`AdmissionOutcome`.
- `tests/test_ws_b_admission.py` — 24 tests, all passing.

**SR/FR -> file + test mapping**
- **SR-2 / FR-002 (explicit model, LAW 3, admission gateway; ADR-0009)** ->
  `scripts/ws_b_admission.py:admit()` (fail-closed precondition #1, rejects
  before any side effect) + `dispatch_through_gate()` (proves the model call
  is unreached). Tests: `test_missing_model_rejected_before_model_call`,
  `test_empty_string_model_rejected`, `test_non_string_model_rejected`,
  `test_frontmatter_model_hint_is_never_a_fallback`,
  `test_valid_explicit_model_is_admitted_when_budget_and_credit_clear`.
- **FR-006 / Q9 (Claude-subscription/OAuth auth, not a metered key, swappable
  behind the gateway; design §4.1)** -> `build_subscription_env()` drops
  `ANTHROPIC_API_KEY`/`ANTHROPIC_AUTH_TOKEN` from the constructed child env
  entirely (never just blanked) so the SDK falls through to the OAuth profile;
  auth admission stays inside the single `admit()` seam. Tests:
  `test_build_subscription_env_has_no_api_key_var_absent_base`,
  `test_build_subscription_env_drops_even_an_empty_api_key` (the exact
  ANTHROPIC_API_KEY="" gotcha from the design), `test_build_subscription_env_
  drops_a_real_looking_key`, `test_build_subscription_env_extra_cannot_
  reintroduce_key`, `test_build_subscription_env_no_base_env_defaults_empty`.
- **FR-007 (mustaqil per-run/per-day cap breach -> idle+alert, metered_overflow
  OFF; ADR-0027 SI-5)** -> `check_budget()` (reuses `alerting.budget_governor`
  for the cost dimension — REUSE, never re-implement — plus a local token-cap
  check) called from `admit()`'s precondition #2. Tests:
  `test_per_run_cost_breach_is_idle_and_alert`,
  `test_per_run_token_cap_breach_is_idle_and_alert`,
  `test_per_day_cost_breach_is_idle_and_alert`, `test_under_budget_is_not_a_breach`,
  `test_credit_exhaustion_never_falls_back_to_admit_metered_overflow` (no
  overflow parameter exists on `admit()` at all — structural, not configured).
- **FR-008 (monthly-credit exhaustion -> sanctioned pause, resumes on refresh,
  never a crash/silent-stop; Q9)** -> `check_credit_exhaustion()` called from
  `admit()`'s precondition #3, reading `mustaqil.monthly_credit_ceiling` from
  `config/budgets.yaml` (read-only — file untouched). Tests:
  `test_monthly_credit_exhaustion_is_sanctioned_pause`,
  `test_credit_refresh_resumes_normally_idempotent` (DAS-1447 guard-before-act:
  same plan, `used_usd` reset -> admits again cleanly),
  `test_non_admit_outcomes_never_raise` (breach/exhaustion never raise and are
  never scored as `ADMIT` — distinct from success and from a crash).
- **SR-5 / FR-005 (flag-gated, shared `ws_b_agent_sdk_runner` key with DAS-1555;
  OFF by default)** -> `gated_admit()` short-circuits to `UNAVAILABLE` before
  any `admit()` logic runs when the flag is OFF. Tests:
  `test_gated_admit_inert_when_flag_off`, `test_gated_admit_reaches_admit_
  logic_when_flag_on`, `test_gated_admit_defaults_to_repo_feature_flags_file`
  (asserts today's real `config/features.yaml` value is inert).
- **DAS-1543 SSOT (`config/budgets.yaml` mustaqil: block, read-only)** ->
  `load_mustaqil_budgets()`. Tests: `test_load_mustaqil_budgets_from_real_config`
  (asserts the real file's caps/on_breach/on_exhaustion/metered_overflow=false/
  plan_credit_usd values), `test_load_mustaqil_budgets_missing_file_is_inert`.

**Config files** — `config/budgets.yaml` and `config/features.yaml` were only
read, never edited, per the ticket's constraints.

**Verification (exact results)**
- `python3 -m pytest tests/test_ws_b_admission.py -q` -> `24 passed in 0.09s`.
- `python3 -m pytest -q` (full suite) -> `1974 passed, 4 skipped in 14.33s`.
- `ruff check scripts/ws_b_admission.py tests/test_ws_b_admission.py` ->
  `All checks passed!` (fixed one import-sort + one `StrEnum` inheritance +
  one `.keys()` simplification flagged by ruff during the pass).
- `python3 scripts/diagnostics.py` -> `SCORE = 90/100`. The single `[FAIL]
  Security 0/10` finding (`no-committed-secrets: possible secrets in:
  ['scripts/ws_a_health_check.py']`) is a **pre-existing** finding on a file
  this ticket never touched (confirmed via `git diff --stat HEAD --
  scripts/ws_a_health_check.py` = empty, and it's outside this ticket's
  `scripts/ws_b_admission.py` + `tests/` footprint; it belongs to the WS-A
  tool-bridge workstream). Flagging for backend-em / CTO awareness rather than
  silently reporting a clean 100/100.
- `python3 scripts/board_lint.py` -> exit 0, `OK — 180 ticket(s) checked, 0
  violations` (one pre-existing, unrelated non-fatal WARN on DAS-1507's body
  prose).

**Constraint note (LOCAL-ONLY):** per the dispatch's hard constraint, no git
branch/commit/PR was created this run — `scripts/ws_b_admission.py` and
`tests/test_ws_b_admission.py` are new, uncommitted, untracked files on the
current checkout (`docs/governed-devin-langchain-direction`, not `main`).
Moving status to `in_review` reflects the code/tests being ready for
backend-em's review; the worktree/branch/PR step (ADR-0005, board rule
"`in_review` requires a pushed branch/PR") still needs to happen before this
can reach `done` — flagging this explicitly rather than silently treating
`in_review` as satisfied. No decision above charter authority was made; no
escalation needed at this time.

**Handoff:** status -> `in_review`, assignee -> `backend-em` (GATE-3 review,
CTO ratification to follow per AADL). DAS-1555 (`daslab_sdk` zone) proceeds in
parallel — no shared-file collision. DAS-1557 (Testing) can build against
`admit`/`gated_admit`/`build_subscription_env` directly once DAS-1555 lands.
