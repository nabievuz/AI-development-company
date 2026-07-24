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
