# WS-H CONTROL health/eval — AADL Stage 6 Maintenance (GATE-6)

> Closes GATE-6 for WS-H CONTROL (ADR-0039 self-hosted web control plane /
> `docs/design/ws-h-control-plane.md`). Accountable: COO. Responsible:
> Product Analyst. Consulted: Support Lead. Ticket: DAS-1605.

## What this is

A **recurring, read-only** health/eval check for the WS-H self-hosted web
control plane surface — RBAC (Founder-only gate approval and run triggering),
audit-trail redaction, the degrade-to-static default, and the bearer-token
comparison discipline — wired into the **existing** Maintenance-stage cadence
(`scripts/stage_gate.py: maintenance_schedule()`) rather than a new daemon or
scheduler. Per the AI-agent-lifecycle policy §3 (Stage 6), the schedule
descriptor is **data, not an installer** — cadence lives in the Founder-owned
OS scheduler entry (ADR-0027 SI-1); nothing here deploys, auto-runs itself, or
flips the `ws_h_control_plane` flag.

Check script: `scripts/ws_h_health_check.py`
Registered as the `ws-h-control-health` entry in `maintenance_schedule()`'s
`recurring_runs` list, alongside `health-tick` (WS4), `golden-eval` (WS6),
`memory-hygiene` (ArcRift), `ws-a-tool-edge-health` (WS-A),
`ws-b-runner-health` (WS-B), `ws-c-loop-health` (WS-C), `ws-d-lens-health`
(WS-D), and `ws-e-tenant-health` (WS-E) — this is the final workstream health
entry for the mustaqil program, no second scheduling mechanism was
introduced.

## What it checks

1. **RBAC drift** — reuses `scripts/rbac.py: decide()` (no fork) to assert
   `decide("agent:<any-role>", "gate.approve")` AND
   `decide("agent:<any-role>", "run.trigger")` are still `deny`, and reuses
   `scripts/rbac.py: load_grants()` to assert `config/rbac.yaml` still grants
   both permissions ONLY to the `founder` kind. `load_grants()` itself raises
   `RbacConfigError` on a structurally tampered file (a founder-only
   permission granted to a non-founder kind) — this check surfaces that
   refusal as a finding rather than swallowing it. A config change that
   grants `gate.approve` or `run.trigger` to any agent/orchestrator/
   audit-team kind is a finding.
2. **Audit-redaction drift** — reuses `tools/mcp_bridges/redaction.py:
   safe_scrub()` (no fork — the SAME scrubber `tools/control_plane/app.py`'s
   `audit()` helper calls before writing the `detail` field, ADR-0012) by
   feeding it a planted secret-shaped probe and asserting the scrubbed
   output (a) no longer contains the raw secret substring and (b) is not a
   byte-identical passthrough of the input. A regression that lets a raw
   secret/PII value reach the append-only control-plane audit ledger
   (`board/.control-plane-audit.jsonl`) is a finding.
3. **Degrade/flag drift** — reuses `scripts/feature_flags.py: enabled()` to
   assert `ws_h_control_plane` still defaults OFF in `config/features.yaml`,
   and reuses `tools/control_plane/install/degrade.py: resolve_surface()` (no
   fork) to assert the degrade-to-static path still fires: with the flag as
   currently configured (OFF by default) the surface resolves to `"static"`,
   and even with `--force-static` it resolves to `"static"`. A regression
   that returns `"control-plane"` under either condition — or that crashes
   instead of degrading when the optional fastapi/uvicorn deps are absent —
   is a finding (CP-5, NOT-a-daemon).
4. **Token-compare drift** — a **static AST scan** (no import — fastapi is an
   optional dependency this check must not require, so it never imports
   `tools/control_plane/app.py` directly) of the `_match_token()` helper,
   asserting it still calls `hmac.compare_digest` for the bearer-token
   comparison and has not regressed to a bare dict `.get()` lookup (a timing
   side-channel regression on the auth secret). A regression to a plain
   `tokens.get(token)` lookup, or the removal of the `compare_digest` call
   entirely, is a finding.

## Cadence and registration

- **Cadence:** daily (declared in `maintenance_schedule()["recurring_runs"]`,
  entry `ws-h-control-health`).
- **Command:** `python3 scripts/ws_h_health_check.py --json`.
- **Exit code:** `0` = healthy; `1` = a finding (RBAC drift, audit-redaction
  drift, degrade/flag drift, and/or token-compare drift) — the caller MUST
  treat this as an alert, never swallow it.
- Same registration point every other Maintenance-stage run uses — no
  second scheduling mechanism was introduced.

## Alerting — a failure is never silent

A non-zero exit from `scripts/ws_h_health_check.py` is treated the same way
any other Maintenance-cadence finding is treated:

1. The run's output (`--json`) is attached as evidence.
2. A follow-up board ticket is filed in `board/tickets/` (org-engine scope —
   this is a platform/governance concern, not a project) with
   `labels: [security]`, `dept: engineering`, routed per
   `governance/policies/raci.md` (Security Lead consulted, SRE/COO informed) —
   the same path DAS-1551/DAS-1559/DAS-1569/DAS-1577/DAS-1587 used for the
   earlier workstream findings.
3. The ticket is **never** auto-remediated: fixing an RBAC drift means
   correcting `config/rbac.yaml` back to the founder-only grant for
   `gate.approve`/`run.trigger` (a `security_sensitive` +
   `governance_or_policy` + `permission_change` change — QONUN-5 forbids
   `approval: auto*` on it); fixing an audit-redaction drift means restoring
   the `tools/mcp_bridges/redaction.py` scrubber call path in
   `tools/control_plane/app.py: audit()`; fixing a degrade/flag drift means
   restoring the flag-OFF default in `config/features.yaml` or the
   fail-closed logic in `tools/control_plane/install/degrade.py:
   resolve_surface()`; fixing a token-compare drift means restoring the
   `hmac.compare_digest` comparison in `tools/control_plane/app.py:
   _match_token()`. All are `security_sensitive`/`governance_or_policy`
   categories per `config/risk_taxonomy.yaml` — CI's never-auto-approve
   check (`scripts/check_never_auto_approve.py`) rejects an
   `approval: auto*` on any of them. The `ws_h_control_plane` feature flag
   itself is never touched by this check or by its remediation.

## Founder-reviewed learnings → `daslab-learn` (ADR-0029 G5)

A **repeated or systemic** finding from this check (e.g. the same drift
class recurring, or an RBAC/redaction/degrade/token-compare gap found more
than once) is a candidate **lesson**, not just a one-off ticket. Per ADR-0029
§G5, lessons flow through the existing `daslab-learn` distillation:

- The finding + its accepted remediation is logged in the relevant ticket
  (this doc's §Alerting above).
- `daslab-learn` distills **Founder-accepted** feedback only into a role's
  `## Learned` section (bounded, confidence-scored) — it is **governed
  compounding**, never autonomous self-modification. This health check does
  not write to any `## Learned` section itself; it only produces evidence
  for a human (Founder/CPO/Security Lead) to accept or reject at the normal
  `daslab-learn` cadence.
- Likely destination roles: `security-lead` (RBAC / token-comparison /
  audit-redaction patterns) and `sre-lead` (degrade-to-static / flag-default
  patterns) per `governance/agent-templates/*.md` overlays — routing the
  specific lesson to a role is a `daslab-learn` decision, not this script's.

## Verification

```
python3 scripts/ws_h_health_check.py            # human-readable
python3 scripts/ws_h_health_check.py --json      # machine-readable, for the alert payload
python3 -m pytest tests/test_ws_h_health_check.py -q
```
