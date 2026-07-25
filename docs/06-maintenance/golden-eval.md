# Golden-eval — AADL Stage 6 Maintenance (GATE-6)

> The WS6 recurring eval run. Accountable: QA Lead (GATE-4/GATE-6 eval
> thresholds). Consulted: CTO. Origin ticket: DAS-1487 (WS6 GUILD / P19).
> Runbook authored: DAS-1631.

## What this is

A **recurring, read-only** golden-eval run that scores each agent role's real
competence and cost against a curated golden-task set, wired into the
**existing** Maintenance-stage cadence
(`scripts/stage_gate.py:maintenance_schedule()`) rather than a new daemon or
scheduler. Per the AI-agent-lifecycle policy §3 (Stage 6), the schedule
descriptor is **data, not an installer** — cadence lives in the Founder-owned OS
scheduler entry (ADR-0027 SI-1); nothing here deploys, auto-runs itself, or
changes any role's tier or model.

Check script: `scripts/agent_eval.py`
Registered as the `golden-eval` entry in `maintenance_schedule()`'s
`recurring_runs` list, alongside `health-tick` (WS4), `memory-hygiene`
(ArcRift), and the per-workstream `ws-*-health` checks.

## What it does

`scripts/agent_eval.py` walks the `evals/<role>/<task-id>/` tree — one directory
per golden task, each with a task prompt, input fixtures, and a **deterministic**
`verify.py` that returns fractional credit in `[0.0, 1.0]`. It produces a
scorecard ranking roles (and their allocated models) on **evidence**, not
reputation: measured accuracy against the golden set plus measured cost. The
`--roster` mode confirms every role in `board/ROUTING.md` has at least one
golden task registered (no un-evaluated role).

## Cadence and registration

- **Cadence:** daily (declared in `maintenance_schedule()["recurring_runs"]`,
  entry `golden-eval`).
- **Command:** `python3 scripts/agent_eval.py`.
- **Exit code / output:** a read-only scorecard. A regression against a prior
  accuracy bar is a **finding**, surfaced for a human — never a silent tier or
  model change.
- Same registration point every other Maintenance-stage run uses — no second
  scheduling mechanism was introduced.

## Why it carries no `command[1]` script-path caveat

Its `command` is a plain `python3 <script>` invocation
(`["python3", "scripts/agent_eval.py"]`), so `command[1]` resolves to a real
file on disk exactly like the `ws-*-health` checks. It is a fully script-backed
run; the only thing it historically lacked was this linked runbook, which
DAS-1631 supplies so `config` (the runbook link) can be universal across the
schedule.

## Alerting — a regression is never silent

A golden-eval regression (an accuracy drop below a role's prior bar) is handled
the same way any other Maintenance-cadence finding is:

1. The scorecard output is attached as evidence.
2. A follow-up board ticket is filed in `board/tickets/` (org-engine scope),
   routed per `governance/policies/raci.md`.
3. The finding is **never** auto-remediated: any tier promotion, model
   reallocation, or eval-threshold change is `governance_or_policy` /
   never-auto-approve (`config/risk_taxonomy.yaml`) and waits for a human
   (GATE-6 sign-off, QONUN-5 / ADR-0027 SI-7). This run never edits
   `governance/policies/model-allocation.md` or any role overlay itself.

## Verification

```
python3 scripts/agent_eval.py                 # human-readable scorecard
python3 scripts/agent_eval.py --roster        # every routed role has a golden task
python3 -m pytest tests/test_agent_eval.py -q
```
