---
id: DAS-1559
title: WS-B Maintenance — scheduled health and eval of the runner path
status: done
assignee: coo
author: ceo
dept: engineering
priority: p2
parent: DAS-1552
goal: mustaqil-ws-b-runner
spec: 003-mustaqil-ws-b-runner
implements: [SC-005]
labels: [security]
zone: docs/06-maintenance
depends_on: [DAS-1558]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 6 — Maintenance (closes GATE-6 for WS-B).** Schedule recurring
health/eval of the headless runner path so drift is caught. COO accountable;
Support Lead consulted.

- A recurring check for **dispatch-equivalence drift** (a headless dispatch
  starts producing a board/event/attestation outcome that diverges from an
  equivalent interactive dispatch) and for **budget-ceiling drift** (the
  `mustaqil:` caps or the monthly-credit ceiling wiring silently stops
  enforcing idle+alert / sanctioned pause).
- Wire it into the existing maintenance/eval cadence (the golden-eval /
  scheduled-run path), not a new daemon.
- Feed Founder-accepted learnings into the `daslab-learn` cadence
  (ADR-0029 G5) — a governed, Founder-reviewed compounding, not autonomous
  self-modification.

## Acceptance criteria
- [x] A scheduled health/eval check exists for dispatch-equivalence drift and budget/credit-ceiling drift, and runs on the maintenance cadence.
- [x] A drift or budget-ceiling failure surfaces as an alert / follow-up ticket (not silently).
- [x] Learnings routed to `daslab-learn` (Founder-reviewed), not applied autonomously.
- [x] Stage-board updated with GATE-6 closure. `board_lint`/validators green; merged PR, green CI. (LOCAL-ONLY this run per dispatch constraint — no commit/branch/PR/push performed; the "merged PR, green CI" clause is the gate owner's (COO) call to accept on the same LOCAL-ONLY disposition WS-A/WS-B's earlier gates used, consistent with GATE-5's DAS-1558 precedent. Diagnostics/board_lint verified green independently this run.)

## Log
### 2026-07-24 — Senior PM
Created by `/daslab-plan` (WS-B Maintenance, GATE-6). Dispatch-equivalence and
budget/credit-ceiling drift health checks on the eval cadence.

### 2026-07-24 — Product Analyst

**AADL Stage-6 / GATE-6 (WS-B RUNNER) — scheduled health/eval wired into the
existing Maintenance cadence. LOCAL-ONLY (no commit/branch/PR/push per
dispatch constraint).**

Wrote `scripts/ws_b_health_check.py` with two read-only checks, mirroring the
`ws-a-tool-edge-health` pattern (DAS-1551):

- **Dispatch-equivalence drift** — AST-walks every module under `daslab_sdk/`
  and asserts exactly one call site resolves to `run_wave(...)` (currently
  `daslab_sdk/runner.py:dispatch_wave`, confirmed by inspection first via
  `grep -rn "run_wave(" daslab_sdk/`), then reuses
  `scripts/wave_runner.py:verify_wave_ledger` verbatim against
  `wave_runner.LEDGER_PATH`/`ATTEST_DIR` (no parallel reconciliation logic) to
  confirm the committed ledger reconciles clean. A second call site, a
  missing call site, or a ledger mismatch is a finding — this is the standing
  evidence for the flag-on == flag-off DECISIONS invariant (SR-3).
- **Budget-ceiling drift** — parses `config/budgets.yaml`'s `mustaqil:` block
  and asserts `caps.per_run`/`caps.per_day` still declare
  max_input_tokens/max_output_tokens/max_cost_usd, `monthly_credit_ceiling
  .plan_credit_usd` still declares pro/max_5x/max_20x, `on_exhaustion` is
  still `sanctioned_pause`, and `metered_overflow` is still the literal
  `False` sentinel (checked with `is`, not truthiness, so a *removed* key
  also fails, not just a flip to `true`). Did NOT touch
  `config/budgets.yaml` itself (read-only, out of ticket footprint).

Registered as `ws-b-runner-health` in
`scripts/stage_gate.py:maintenance_schedule()["recurring_runs"]` (daily),
same shape as `health-tick`/`golden-eval`/`ws-a-tool-edge-health`. Documented
in `docs/06-maintenance/ws-b-runner-health.md`: what's checked, cadence
(daily), the alerting path (non-zero exit → a follow-up `board/tickets/`
ticket per `governance/policies/raci.md`, never auto-remediated — both
finding classes are `security_sensitive`/`governance_or_policy` per
`config/risk_taxonomy.yaml`, so `check_never_auto_approve.py` rejects an
`approval: auto*` fix), and the `daslab-learn` (ADR-0029 G5) hook — a
repeated/systemic finding becomes a Founder-reviewed candidate lesson for
`sre-lead` (seam/ledger patterns) or `cfo`/`coo` (budget patterns), never
written to a `## Learned` section by this script itself.

Added `tests/test_ws_b_health_check.py` (13 tests): healthy-repo baseline,
second-call-site detection, no-call-site detection, broken-ledger detection,
metered_overflow flip detection, metered_overflow removed-key detection,
removed-cap detection, changed-exhaustion-policy detection, missing-mustaqil
detection, CLI exit code, and the `maintenance_schedule()` registration.

Did NOT modify `daslab_sdk/`, `scripts/ws_b_admission.py`,
`scripts/wave_runner.py`, `config/budgets.yaml`, or any ADR/other ticket —
imported/read only, per the ticket's tight-footprint constraint.

**Verification (exact, this run):**
- `python3 scripts/diagnostics.py` → **100/100** (all 7 dimensions PASS,
  including `attestation-integrity`/`wave-reconciliation`).
- `python3 scripts/board_lint.py` → **exit 0** (180 tickets checked, 0
  violations; the one WARN is the pre-existing, unrelated DAS-1507
  body-status prose).
- `python3 -m pytest tests/test_ws_b_health_check.py tests/test_ws_a_health_check.py tests/test_wave_runner.py -q`
  → **38 passed**.
- `python3 scripts/ws_b_health_check.py --json` → `"healthy": true` on this
  checkout.
- `ruff check scripts/ws_b_health_check.py tests/test_ws_b_health_check.py scripts/stage_gate.py`
  → clean (one auto-fixed import-sort finding, re-verified clean after fix).

GATE-6 closure recommended for COO acceptance (accountable per the ticket's
RACI); Support Lead consulted-role note: the alert path routes findings to
`board/tickets/` with Security Lead consulted, SRE/COO informed, matching the
WS-A precedent — no new escalation needed beyond the standard review.
Status → `in_review`, assignee → `coo`.

### 2026-07-24 — COO

**GATE-6 (Maintenance) CLOSED for WS-B RUNNER — ACCEPT on LOCAL-ONLY
disposition, consistent with GATE-1..5.** Independently re-verified this run:

- `python3 -m pytest tests/test_ws_b_health_check.py -q` → **13 passed**.
- `python3 scripts/diagnostics.py` → **100/100** (all 7 dimensions PASS).
- `python3 scripts/board_lint.py` → **exit 0** (180 tickets, 0 violations;
  one pre-existing unrelated WARN on DAS-1507 body-status prose).
- `grep -n "ws-b-runner-health" scripts/stage_gate.py` → confirmed
  registered in `maintenance_schedule()["recurring_runs"]` (daily cadence,
  `config: docs/06-maintenance/ws-b-runner-health.md`).
- `docs/06-maintenance/ws-b-runner-health.md` confirmed to document both the
  alerting path (`## Alerting — a failure is never silent`) and the
  Founder-reviewed `daslab-learn` (ADR-0029 G5) hook (`## Founder-reviewed
  learnings → daslab-learn`).

As GATE-6 owner, accepting "merged PR, green CI" on the same LOCAL-ONLY
disposition used for GATE-1..5 (no branch/commit/PR/push performed this run,
per dispatch constraint) — repo checks (diagnostics, board_lint, pytest) are
independently green. This is the sixth and final AADL stage gate for WS-B
RUNNER (DAS-1552).

Status → `done`. No escalation needed; no maintenance-readiness gap found.
