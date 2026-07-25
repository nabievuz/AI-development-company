# WS-B runner health/eval — AADL Stage 6 Maintenance (GATE-6)

> Closes GATE-6 for WS-B RUNNER (ADR-0034). Accountable: COO. Responsible:
> Product Analyst. Consulted: Support Lead. Ticket: DAS-1559.

## What this is

A **recurring, read-only** health/eval check for the headless Agent SDK runner
(`daslab_sdk/`, ADR-0034), wired into the **existing** Maintenance-stage
cadence (`scripts/stage_gate.py:maintenance_schedule()`) rather than a new
daemon or scheduler. Per the AI-agent-lifecycle policy §3 (Stage 6), the
schedule descriptor is **data, not an installer** — cadence lives in the
Founder-owned OS scheduler entry (ADR-0027 SI-1); nothing here deploys or
auto-runs itself, and nothing here flips the `ws_b_agent_sdk_runner` flag.

Check script: `scripts/ws_b_health_check.py`
Registered as the `ws-b-runner-health` entry in `maintenance_schedule()`'s
`recurring_runs` list, alongside `health-tick` (WS4), `golden-eval` (WS6),
`memory-hygiene` (ArcRift), and `ws-a-tool-edge-health` (WS-A).

## What it checks

1. **Dispatch-equivalence drift** — statically AST-walks every module under
   `daslab_sdk/` for a call that resolves to `run_wave(...)` and asserts
   exactly **one** call site exists (currently `daslab_sdk/runner.py:
   dispatch_wave`), then reuses `scripts/wave_runner.py:verify_wave_ledger`
   verbatim (no parallel reconciliation logic) to confirm the committed wave
   ledger still reconciles clean (0 problems). Together these are the
   standing evidence for the **flag-on == flag-off DECISIONS invariant**
   (ADR-0034 SR-3): the headless runner is a *new caller* of the one
   post-decision seam, never a second producer of the event/attestation
   stream. A second call site, a missing call site, or a ledger reconciliation
   failure is a finding.
2. **Budget-ceiling drift** — parses `config/budgets.yaml`'s `mustaqil:`
   block and asserts the SI-5 shape is intact: `caps.per_run` and
   `caps.per_day` each still declare `max_input_tokens` /
   `max_output_tokens` / `max_cost_usd`; `monthly_credit_ceiling
   .plan_credit_usd` still declares `pro` / `max_5x` / `max_20x`;
   `on_exhaustion` is still `sanctioned_pause`; and — checked against the
   exact `False` sentinel, not mere falsiness, so a *removed* key also fails
   — `metered_overflow` is still literal `false`. A silent flip of
   `metered_overflow` to `true`, a removed cap, or a changed exhaustion
   policy is a finding: the subscription-only budget stance (Q3/Q9,
   DAS-1543) must not drift quietly.

   The check is implemented in `scripts/ws_b_health_check.py ::
   check_budget_ceiling_drift(path=None)`, which takes an optional `path`
   parameter defaulting to the module global `BUDGETS_PATH`. The semantics
   are unchanged from the direct mode — same parse, same findings, same
   strict `metered_overflow is False` identity guard. The `path` parameter
   exists so a composing caller (see §Load-bearing use in heartbeat go/no-go,
   below) can point the one owning predicate at a test budgets file without
   monkeypatching this module.

## Load-bearing use: heartbeat go/no-go (Founder-facing)

The `check_budget_ceiling_drift()` predicate acquired a second, higher-stakes
consumer: `scripts/heartbeat_go_no_go.py` (DAS-1619). This script is the
**Founder-facing go/no-go readiness report** for the HEARTBEAT autonomy flip
— an irreversible, one-time decision gate. The function is called directly by
`probe_credit_ceiling_shape()` as gate `credit_semantics` (SI-5/FR-004) in the
gating checks that decide the report's `VERDICT: GO` or `VERDICT: NO-GO`.

**The predicate is now load-bearing: relaxing its guard locally will weaken the
Founder's go-live gate as well as WS-B's own health check.** Specifically:

- `check_budget_ceiling_drift()` is the **sole owner** of the monthly
  credit-ceiling contract. No other code in `heartbeat_go_no_go.py` parses
  `config/budgets.yaml` fields of its own — the report calls this function and
  reports its verdict verbatim.
- The strict-identity guard (`overflow is not False`) is **deliberate and must
  not be relaxed**. It treats a *removed* `metered_overflow` key the same as a
  flip to `true` — both are findings. A removed key silently re-enables metered
  spend, which is exactly the bug the guard exists to catch. A lax truthiness
  check (`if overflow:`) would miss a removed key and incorrectly pass the gate.
- **A test in the go/no-go suite will fail if the guard is weakened.** The test
  suite (`tests/test_heartbeat_go_no_go.py`) verifies the gate's verdict on
  a scratch budgets file. If the guard is locally "simplified" to a lax check,
  that test will go red. The failure may look unrelated to the local change
  (because the test file name does not mention budgets), but the root cause
  will be the guard relaxation.

A WS-B maintainer reading only this doc — and not `heartbeat_go_no_go.py` —
now knows that `check_budget_ceiling_drift()` is not just a health check, but a
Founder-facing decision predicate. Any change to it must be reviewed for its
impact on the go-live gate.

## Cadence and registration

- **Cadence:** daily (declared in `maintenance_schedule()["recurring_runs"]`,
  entry `ws-b-runner-health`).
- **Command:** `python3 scripts/ws_b_health_check.py --json`.
- **Exit code:** `0` = healthy; `1` = a finding (drift and/or a ledger/budget
  mismatch) — the caller MUST treat this as an alert, never swallow it.
- Same registration point every other Maintenance-stage run uses (WS4
  `health-tick`, WS6 `golden-eval`, ArcRift `memory-hygiene`, WS-A
  `ws-a-tool-edge-health`) — no second scheduling mechanism was introduced.

## Alerting — a failure is never silent

A non-zero exit from `scripts/ws_b_health_check.py` is treated the same way
any other Maintenance-cadence finding is treated:

1. The run's output (`--json`) is attached as evidence.
2. A follow-up board ticket is filed in `board/tickets/` (org-engine scope —
   this is a platform/governance concern, not a project) with
   `labels: [security]`, `dept: engineering`, routed per
   `governance/policies/raci.md` (Security Lead consulted, SRE/COO informed) —
   the same path DAS-1547/1549/1551 used for WS-A findings.
3. The ticket is **never** auto-remediated: a dispatch-equivalence finding
   means a human reviews and fixes the second call site (or the ledger gap)
   before any further wave dispatch; a budget-ceiling finding means a human
   reviews the `config/budgets.yaml` diff and restores or explicitly
   re-approves the change. Both are `security_sensitive` /
   `governance_or_policy` categories per `config/risk_taxonomy.yaml` — CI's
   never-auto-approve check (`scripts/check_never_auto_approve.py`) rejects an
   `approval: auto*` on either. The runner flag itself is never touched by
   this check or by its remediation.

## Founder-reviewed learnings → `daslab-learn` (ADR-0029 G5)

A **repeated or systemic** finding from this check (e.g. the same drift class
recurring, or a budget cap regressed more than once) is a candidate
**lesson**, not just a one-off ticket. Per ADR-0029 §G5, lessons flow through
the existing `daslab-learn` distillation:

- The finding + its accepted remediation is logged in the relevant ticket
  (this doc's §Alerting above).
- `daslab-learn` distills **Founder-accepted** feedback only into a role's
  `## Learned` section (bounded, confidence-scored) — it is **governed
  compounding**, never autonomous self-modification. This health check does
  not write to any `## Learned` section itself; it only produces evidence for
  a human (Founder/CPO/Security Lead) to accept or reject at the normal
  `daslab-learn` cadence.
- Likely destination roles: `sre-lead` (dispatch-seam / ledger-integrity
  patterns) and `cfo`/`coo` (budget-ceiling patterns) per
  `governance/agent-templates/*.md` overlays — routing the specific lesson to
  a role is a `daslab-learn` decision, not this script's.

## Verification

```
python3 scripts/ws_b_health_check.py            # human-readable
python3 scripts/ws_b_health_check.py --json      # machine-readable, for the alert payload
python3 -m pytest tests/test_ws_b_health_check.py -q
```
