# WS-A tool-edge health/eval — AADL Stage 6 Maintenance (GATE-6)

> Closes GATE-6 for WS-A REACH (ADR-0033). Accountable: COO. Responsible:
> Product Analyst. Consulted: Support Lead. Ticket: DAS-1551.

## What this is

A **recurring, read-only** health/eval check for the governed tool edge (the
`langchain-tools` / `browser` MCP bridge, `tools/mcp_bridges/*`, ADR-0033),
wired into the **existing** Maintenance-stage cadence
(`scripts/stage_gate.py:maintenance_schedule()`) rather than a new daemon or
scheduler. Per the AI-agent-lifecycle policy §3 (Stage 6), the schedule
descriptor is **data, not an installer** — cadence lives in the Founder-owned
OS scheduler entry (ADR-0027 SI-1); nothing here deploys or auto-runs itself.

Check script: `scripts/ws_a_health_check.py`
Registered as the `ws-a-tool-edge-health` entry in `maintenance_schedule()`'s
`recurring_runs` list, alongside the existing `health-tick` (WS4 heartbeat) and
`golden-eval` (WS6) entries.

## What it checks

1. **Allow-list drift** — recompiles `board/.tool-allowlist.json` in memory
   from every role overlay's `## External tools` grant (reusing
   `scripts/gen_subagents.compile_tool_allowlist()` — the exact SSOT compiler,
   no parallel logic) and diffs it against the tracked file on disk. This is a
   *targeted* re-check of the same generate-and-diff discipline CI already
   enforces on every push (`.github/workflows/ci.yml`: `gen_subagents.py &&
   git diff --exit-code`, DAS-1547 C1) — it lets the Maintenance cadence catch
   drift introduced any other way (a hand-edit of the compiled JSON, a stale
   checkout, a role granted outside the documented overlay path) on its own
   schedule, independent of a push happening.
2. **Redaction probe** — feeds a battery of known secret-shaped strings (JWT,
   `Bearer` token, DSN with credentials, Anthropic API key, AWS key id, PEM
   private-key block) through the ADR-0012 §2 scrubber
   (`tools/mcp_bridges/redaction.py: safe_scrub`) and asserts every one comes
   back redacted — plus a Tier-M control (a plain git-SHA-shaped string) that
   must **not** be over-redacted, per the ADR-0012 tuning note. This confirms
   tool events stay redacted in practice, not just by code inspection.

## Cadence and registration

- **Cadence:** daily (declared in `maintenance_schedule()["recurring_runs"]`,
  entry `ws-a-tool-edge-health`).
- **Command:** `python3 scripts/ws_a_health_check.py --json`.
- **Exit code:** `0` = healthy; `1` = a finding (drift and/or a redaction
  probe miss) — the caller MUST treat this as an alert, never swallow it.
- This is the same registration point every other Maintenance-stage run uses
  (WS4 `health-tick`, WS6 `golden-eval`, ArcRift `memory-hygiene`) — no second
  scheduling mechanism was introduced.

## Alerting — a failure is never silent

A non-zero exit from `scripts/ws_a_health_check.py` is treated the same way
any other Maintenance-cadence finding is treated:

1. The run's output (`--json`) is attached as evidence.
2. A follow-up board ticket is filed in `board/tickets/` (org-engine scope —
   this is a platform/governance concern, not a project) with
   `labels: [security]`, `dept: engineering`, routed per
   `governance/policies/raci.md` (Security Lead consulted, SRE/COO informed) —
   the same path DAS-1547/1549 used for WS-A findings.
3. The ticket is **never** auto-remediated: fixing a drifted allow-list means
   re-running `scripts/gen_subagents.py` and reviewing the diff by a human (a
   `security_sensitive` change per `config/risk_taxonomy.yaml`); fixing a
   redaction miss means a scrubber-pattern change, also human-reviewed. Both
   are `governance_or_policy` / `security_sensitive` categories — CI's
   never-auto-approve check (`scripts/check_never_auto_approve.py`) rejects an
   `approval: auto*` on either.

## Founder-reviewed learnings → `daslab-learn` (ADR-0029 G5)

A **repeated or systemic** finding from this check (e.g. the same drift class
recurring, or a redaction pattern gap found more than once) is a candidate
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
- Likely destination roles: `security-lead` (allow-list / egress drift
  patterns) and `sre-lead` (redaction / observability patterns) per
  `governance/agent-templates/*.md` overlays — routing the specific lesson to
  a role is a `daslab-learn` decision, not this script's.

## Verification

```
python3 scripts/ws_a_health_check.py            # human-readable
python3 scripts/ws_a_health_check.py --json      # machine-readable, for the alert payload
python3 -m pytest tests/test_ws_a_health_check.py -q
```
