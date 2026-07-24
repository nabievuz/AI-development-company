# WS-D LENS health/eval — AADL Stage 6 Maintenance (GATE-6)

> Closes GATE-6 for WS-D LENS (ADR-0036 / ADR-0033). Accountable: COO.
> Responsible: Product Analyst. Consulted: Support Lead. Ticket: DAS-1577.

## What this is

A **recurring, read-only** health/eval check for the observability lens (the
self-host Langfuse OTLP exporter, ADR-0036) and the eval-tool admission edge
(promptfoo/AgentShield/Presidio, ADR-0033), wired into the **existing**
Maintenance-stage cadence (`scripts/stage_gate.py:maintenance_schedule()`)
rather than a new daemon or scheduler. Per the AI-agent-lifecycle policy §3
(Stage 6), the schedule descriptor is **data, not an installer** — cadence
lives in the Founder-owned OS scheduler entry (ADR-0027 SI-1); nothing here
deploys, auto-runs itself, or flips the `ws_d_langfuse_lens` flag.

Check script: `scripts/ws_d_health_check.py`
Registered as the `ws-d-lens-health` entry in `maintenance_schedule()`'s
`recurring_runs` list, alongside `health-tick` (WS4), `golden-eval` (WS6),
`memory-hygiene` (ArcRift), `ws-a-tool-edge-health` (WS-A), and
`ws-b-runner-health` (WS-B).

## What it checks

1. **Redaction-on-export drift** — feeds a battery of known secret-shaped
   span attributes (a `Bearer` token, a DSN with credentials, an Anthropic
   API key, an AWS key id) through the exporter's own
   `tools/observability/otlp_exporter.py: redact_span` (which wraps the
   ADR-0012 §2 scrubber, `tools/mcp_bridges/redaction.py`, no fork) and
   asserts every Tier-B attribute comes back redacted, while the Tier-M ids
   (`span_id` / `trace_id`) survive untouched — a redaction miss on either
   direction is a finding.
2. **In-tenant target drift** — reuses the exporter's own
   `assert_in_tenant()`, which itself reuses `scripts/check_in_tenant.py`
   verbatim (no parallel boundary logic), to confirm the
   `langfuse_observability` endpoint in `config/tenant_boundary.yaml` still
   resolves in-tenant. A hosted Langfuse Cloud / LangSmith URL slipping into
   that endpoint is a finding.
3. **Eval-tool allow-list drift** — recompiles `board/.tool-allowlist.json`
   in-memory via `scripts/gen_subagents.py: compile_tool_allowlist()` (the
   exact SSOT compiler WS-A's DAS-1551 check already reuses — no duplicate
   allow-list mechanism), diffs it against the tracked file, confirms the
   promptfoo/AgentShield/Presidio grants are still present, and asserts no
   compiled entry ever carries a literal `"*"` role (C2: only explicit role
   keys are ever emitted).

## Cadence and registration

- **Cadence:** daily (declared in `maintenance_schedule()["recurring_runs"]`,
  entry `ws-d-lens-health`).
- **Command:** `python3 scripts/ws_d_health_check.py --json`.
- **Exit code:** `0` = healthy; `1` = a finding (redaction miss, in-tenant
  drift, and/or allow-list drift) — the caller MUST treat this as an alert,
  never swallow it.
- Same registration point every other Maintenance-stage run uses (WS4
  `health-tick`, WS6 `golden-eval`, ArcRift `memory-hygiene`, WS-A
  `ws-a-tool-edge-health`, WS-B `ws-b-runner-health`) — no second scheduling
  mechanism was introduced.

## Alerting — a failure is never silent

A non-zero exit from `scripts/ws_d_health_check.py` is treated the same way
any other Maintenance-cadence finding is treated:

1. The run's output (`--json`) is attached as evidence.
2. A follow-up board ticket is filed in `board/tickets/` (org-engine scope —
   this is a platform/governance concern, not a project) with
   `labels: [security]`, `dept: engineering`, routed per
   `governance/policies/raci.md` (Security Lead consulted, SRE/COO informed) —
   the same path DAS-1551/DAS-1559 used for WS-A/WS-B findings.
3. The ticket is **never** auto-remediated: fixing a redaction miss means a
   scrubber-pattern change; fixing an in-tenant drift means correcting the
   `langfuse_observability` endpoint back to a self-host target (never
   pointing it at a hosted service, per FR-006 / ADR-0038 TN-1); fixing an
   allow-list drift means re-running `scripts/gen_subagents.py` and reviewing
   the diff. All three are `security_sensitive` / `governance_or_policy`
   categories per `config/risk_taxonomy.yaml` — CI's never-auto-approve check
   (`scripts/check_never_auto_approve.py`) rejects an `approval: auto*` on
   any of them. The exporter feature flag itself is never touched by this
   check or by its remediation.

## Founder-reviewed learnings → `daslab-learn` (ADR-0029 G5)

A **repeated or systemic** finding from this check (e.g. the same drift class
recurring, or a redaction gap found more than once) is a candidate
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
- Likely destination roles: `sre-lead` (redaction / observability-lens
  patterns) and `security-lead` (in-tenant boundary / eval-tool allow-list
  patterns) per `governance/agent-templates/*.md` overlays — routing the
  specific lesson to a role is a `daslab-learn` decision, not this script's.

## Verification

```
python3 scripts/ws_d_health_check.py            # human-readable
python3 scripts/ws_d_health_check.py --json      # machine-readable, for the alert payload
python3 -m pytest tests/test_ws_d_health_check.py -q
```
