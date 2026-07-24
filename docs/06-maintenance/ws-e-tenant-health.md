# WS-E TENANT health/eval — AADL Stage 6 Maintenance (GATE-6)

> Closes GATE-6 for WS-E TENANT (ADR-0038 self-host program /
> `docs/design/ws-e-tenant-hardening.md`). Accountable: COO. Responsible:
> Product Analyst. Consulted: Support Lead. Ticket: DAS-1587.

## What this is

A **recurring, read-only** health/eval check for the WS-E tenant hardening
surface — RBAC, the model gateway's in-tenant host pin, the TN-1 in-tenant
boundary, and the Presidio/golden-set guardrail chain — wired into the
**existing** Maintenance-stage cadence
(`scripts/stage_gate.py: maintenance_schedule()`) rather than a new daemon or
scheduler. Per the AI-agent-lifecycle policy §3 (Stage 6), the schedule
descriptor is **data, not an installer** — cadence lives in the
Founder-owned OS scheduler entry (ADR-0027 SI-1); nothing here deploys,
auto-runs itself, or flips the `ws_e_tenant_hardening` flag.

Check script: `scripts/ws_e_health_check.py`
Registered as the `ws-e-tenant-health` entry in `maintenance_schedule()`'s
`recurring_runs` list, alongside `health-tick` (WS4), `golden-eval` (WS6),
`memory-hygiene` (ArcRift), `ws-a-tool-edge-health` (WS-A),
`ws-b-runner-health` (WS-B), `ws-d-lens-health` (WS-D), and
`ws-c-loop-health` (WS-C) — this is the final workstream health entry, no
second scheduling mechanism was introduced.

## What it checks

1. **RBAC drift** — reuses `scripts/rbac.py: decide()` (no fork) to assert
   `decide("agent:<any-role>", "gate.approve")` is still `deny`, and reuses
   `scripts/rbac.py: load_grants()` to assert `config/rbac.yaml` still grants
   `gate.approve` / `config.edit.security` (the founder-only permission set,
   `rbac.FOUNDER_ONLY`) ONLY to the `founder` kind. `load_grants()` itself
   raises `RbacConfigError` on a structurally tampered file (a founder-only
   permission granted to a non-founder kind) — this check surfaces that
   refusal as a finding rather than swallowing it. A config change that
   grants `gate.approve` to any agent/orchestrator/audit-team kind is a
   finding.
2. **Gateway host-pin drift** — reuses
   `tools/model_gateway/gateway.py: enforce_boundary()` (no fork) by feeding
   it a rogue `ModelRoute(role="model", url="https://evil-llm.example.com")`
   and asserting it is still refused with `GatewayConfigError`. The
   `accepted_external_roles: [model]` exception in
   `config/tenant_boundary.yaml` pins to the ONE declared `claude_model`
   host, not to every `role="model"` route (R2, GATE-3 residual DAS-1585); a
   regression that stops pinning — i.e. the rogue route is silently
   accepted — is a finding.
3. **In-tenant drift** — reuses `scripts/check_in_tenant.py: evaluate()` (no
   fork) over the tracked `config/tenant_boundary.yaml` to confirm the TN-1
   boundary still holds: every code/IP-carrying endpoint resolves in-tenant,
   the Claude model call remaining the sole accepted external role. Any
   endpoint drifting to a hosted/external target is a finding.
4. **Guardrail/eval drift** — reuses `tools/guardrails/chain.py: guard()`
   (no fork, flag forced on for the probe) to feed a planted PII/secret-shaped
   probe through the Presidio → classifier → policy chain and asserts it
   comes back altered (not a byte-identical passthrough), and reuses
   `evals/ws-e-guardrails/runner.py: run_golden_set()` (no fork) to assert
   the clean golden-set fixture still passes (`judge_eligible` True) while
   the anti-gaming fixture still gates RED (`judge_eligible` False — a
   no-pass never silently becomes a false green, ADR-0020).

## Cadence and registration

- **Cadence:** daily (declared in `maintenance_schedule()["recurring_runs"]`,
  entry `ws-e-tenant-health`).
- **Command:** `python3 scripts/ws_e_health_check.py --json`.
- **Exit code:** `0` = healthy; `1` = a finding (RBAC drift, gateway host-pin
  drift, in-tenant drift, and/or guardrail/eval drift) — the caller MUST
  treat this as an alert, never swallow it.
- Same registration point every other Maintenance-stage run uses — no
  second scheduling mechanism was introduced.

## Alerting — a failure is never silent

A non-zero exit from `scripts/ws_e_health_check.py` is treated the same way
any other Maintenance-cadence finding is treated:

1. The run's output (`--json`) is attached as evidence.
2. A follow-up board ticket is filed in `board/tickets/` (org-engine scope —
   this is a platform/governance concern, not a project) with
   `labels: [security]`, `dept: engineering`, routed per
   `governance/policies/raci.md` (Security Lead consulted, SRE/COO informed) —
   the same path DAS-1551/DAS-1559/DAS-1569/DAS-1577 used for the earlier
   workstream findings.
3. The ticket is **never** auto-remediated: fixing an RBAC drift means
   correcting `config/rbac.yaml` back to the founder-only grant (a
   `security_sensitive` + `governance_or_policy` + `permission_change`
   change — QONUN-5 forbids `approval: auto*` on it); fixing a gateway
   host-pin drift means restoring the declared `claude_model` host pin in
   `enforce_boundary`/`config/tenant_boundary.yaml`; fixing an in-tenant
   drift means correcting the drifted endpoint back to a self-host target
   (never pointing it at a hosted service, per FR-006/ADR-0038 TN-1); fixing
   a guardrail/eval drift means restoring the Presidio redaction path or the
   golden-set anti-gaming gate. All are `security_sensitive` /
   `governance_or_policy` categories per `config/risk_taxonomy.yaml` — CI's
   never-auto-approve check (`scripts/check_never_auto_approve.py`) rejects
   an `approval: auto*` on any of them. The `ws_e_tenant_hardening` feature
   flag itself is never touched by this check or by its remediation.

## Founder-reviewed learnings → `daslab-learn` (ADR-0029 G5)

A **repeated or systemic** finding from this check (e.g. the same drift
class recurring, or an RBAC/host-pin gap found more than once) is a
candidate **lesson**, not just a one-off ticket. Per ADR-0029 §G5, lessons
flow through the existing `daslab-learn` distillation:

- The finding + its accepted remediation is logged in the relevant ticket
  (this doc's §Alerting above).
- `daslab-learn` distills **Founder-accepted** feedback only into a role's
  `## Learned` section (bounded, confidence-scored) — it is **governed
  compounding**, never autonomous self-modification. This health check does
  not write to any `## Learned` section itself; it only produces evidence
  for a human (Founder/CPO/Security Lead) to accept or reject at the normal
  `daslab-learn` cadence.
- Likely destination roles: `security-lead` (RBAC / gateway / in-tenant
  boundary patterns) and `qa-lead` (guardrail/golden-set eval patterns) per
  `governance/agent-templates/*.md` overlays — routing the specific lesson
  to a role is a `daslab-learn` decision, not this script's.

## Verification

```
python3 scripts/ws_e_health_check.py            # human-readable
python3 scripts/ws_e_health_check.py --json      # machine-readable, for the alert payload
python3 -m pytest tests/test_ws_e_health_check.py -q
```
