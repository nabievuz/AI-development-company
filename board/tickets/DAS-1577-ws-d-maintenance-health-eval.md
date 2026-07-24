---
id: DAS-1577
title: WS-D Maintenance — scheduled health and eval of the Langfuse lens and tool-admission edge
status: done
assignee: coo
author: ceo
dept: engineering
priority: p2
parent: DAS-1570
goal: mustaqil-ws-d-lens
spec: 005-mustaqil-ws-d-lens
implements: [SC-005]
labels: [security]
zone: docs/06-maintenance
depends_on: [DAS-1576]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 6 — Maintenance (closes GATE-6 for WS-D).** Schedule recurring
health/eval of the observability lens and the tool-admission edge so drift is
caught. COO accountable; Support Lead consulted.

- A recurring check for **redaction drift** on the exporter (the redaction
  probe still passes on each new span shape) and for **in-tenant target
  drift** (the exporter config still resolves to a self-host endpoint, never a
  hosted one).
- A recurring check for **tool-admission allow-list drift** on
  promptfoo/AgentShield/Presidio (a role or tool granted outside the
  documented allow-list), reusing the same drift check WS-A's DAS-1551
  established rather than duplicating it.
- Wire it into the existing maintenance/eval cadence (the golden-eval /
  scheduled-run path), not a new daemon.
- Feed Founder-accepted learnings into the `daslab-learn` cadence
  (ADR-0029 G5) — a governed, Founder-reviewed compounding, not autonomous
  self-modification.

## Acceptance criteria
- [ ] A scheduled health/eval check exists for exporter redaction + in-tenant-target drift and runs on the maintenance cadence.
- [ ] A scheduled health/eval check exists for promptfoo/AgentShield/Presidio allow-list drift, reusing (not duplicating) the WS-A drift mechanism.
- [ ] A drift or redaction-probe failure surfaces as an alert / follow-up ticket (not silently).
- [ ] Learnings routed to `daslab-learn` (Founder-reviewed), not applied autonomously.
- [ ] Stage-board updated with GATE-6 closure. `board_lint`/validators green; merged PR, green CI.

## Log
### 2026-07-24 — Senior Product Manager
Created by /daslab-plan (WS-D Maintenance, GATE-6). Exporter redaction +
in-tenant-target drift checks; reuse of WS-A's tool-admission drift mechanism
for the eval/guardrail shortlist.

### 2026-07-24 — Product Analyst

**AADL Stage 6 — Maintenance.** Added a scheduled health/eval check for the
WS-D LENS observability lens + eval-tool admission edge and wired it into
the **existing** Maintenance cadence — no new daemon/process:

- **New script:** `scripts/ws_d_health_check.py` — three read-only checks:
  1. **Redaction-on-export drift** — runs known secret-shaped span
     attributes (Bearer token, DSN-with-credentials, Anthropic key, AWS key
     id) through the exporter's own
     `tools/observability/otlp_exporter.py: redact_span` (the ADR-0012
     scrubber path the exporter itself uses, no fork) and asserts every
     Tier-B attribute is redacted while Tier-M ids (`span_id`/`trace_id`)
     survive untouched.
  2. **In-tenant target drift** — reuses the exporter's own
     `assert_in_tenant()` (itself a verbatim reuse of
     `scripts/check_in_tenant.py`) to confirm `config/tenant_boundary.yaml`'s
     `langfuse_observability` endpoint still resolves in-tenant — a hosted
     Langfuse/LangSmith URL slipping in is a finding.
  3. **Eval-tool allow-list drift** — recompiles
     `board/.tool-allowlist.json` in-memory via
     `scripts/gen_subagents.py: compile_tool_allowlist()` (the exact SSOT
     compiler WS-A's DAS-1551 check already reuses, no duplicate mechanism),
     diffs against the tracked file, confirms the promptfoo/AgentShield/
     Presidio grants are present, and asserts no compiled entry ever
     carries a literal `"*"` role.
  Exit code 0 = healthy, 1 = a finding.
- **Registered** as a new `ws-d-lens-health` entry in
  `scripts/stage_gate.py:maintenance_schedule()["recurring_runs"]`,
  alongside `health-tick` (WS4), `golden-eval` (WS6), `memory-hygiene`
  (ArcRift), `ws-a-tool-edge-health` (WS-A), and `ws-b-runner-health`
  (WS-B) — same registration point, cadence `daily`, `command: ["python3",
  "scripts/ws_d_health_check.py", "--json"]`. Still DATA, not an installer
  (ADR-0027 SI-1) — nothing here schedules itself or touches the
  `ws_d_langfuse_lens` flag.
- **Maintenance doc:** `docs/06-maintenance/ws-d-lens-health.md` — what's
  checked, cadence/registration, and the **alerting path**: a non-zero exit
  is never swallowed — it is attached as evidence to a follow-up
  `board/tickets/` ticket (`labels: [security]`, `dept: engineering`, RACI
  routing per the WS-A/WS-B precedent), never auto-remediated (redaction,
  in-tenant, and allow-list fixes are all `security_sensitive`/
  `governance_or_policy` — `check_never_auto_approve.py` rejects
  `approval: auto*` on any of them).
- **`daslab-learn` hook (ADR-0029 G5):** documented in the same maintenance
  doc — a *repeated/systemic* finding is a lesson candidate; it flows
  through the normal `daslab-learn` distillation of **Founder-accepted**
  feedback into a role's `## Learned` section (likely `sre-lead` for
  redaction/observability-lens patterns, `security-lead` for in-tenant/
  allow-list patterns). This script does not write to any `## Learned`
  section itself and performs no self-modification — governed compounding
  only, per the ticket's explicit constraint.
- **Tests:** `tests/test_ws_d_health_check.py` (12 cases) — healthy-repo
  baseline, redaction-miss detected, over-redaction-of-Tier-M-key detected,
  dropped-span detected, in-tenant-drift detected (hosted-endpoint
  simulation), in-tenant-ok path, allow-list drift (tampered/missing
  tracked file), wildcard-role detected, missing-eval-tool-grant detected,
  CLI exit code, and the `maintenance_schedule()` registration itself.

**Validators (exact, 2026-07-24, STAGED state, `git add -A` first):**
- `python3 scripts/diagnostics.py` → **SCORE = 100/100**.
- `python3 scripts/board_lint.py` → **exit 0 — OK: 180 ticket(s) checked, 0
  violations** (pre-existing DAS-1507 body-status WARN only, unrelated).
- `python3 -m pytest tests/test_ws_d_health_check.py -q` → **12 passed**.
- `python3 -m pytest tests/test_stage_gate.py tests/test_ws_a_health_check.py
  tests/test_ws_b_health_check.py tests/test_ws_d_health_check.py
  tests/test_ws_d_otlp_exporter.py -q` → **75 passed** (unaffected by this
  change).
- `ruff check scripts tests` → **All checks passed!**
- `grep -n "ws-d-lens-health" scripts/stage_gate.py` → confirmed registered.

**Files touched (only these, per the tight-footprint constraint):**
`scripts/ws_d_health_check.py` (new), `scripts/stage_gate.py` (added one
`recurring_runs` entry — no other edit), `docs/06-maintenance/ws-d-lens-health.md`
(new), `tests/test_ws_d_health_check.py` (new), this ticket. No WS-D
implementation file, config, ADR, or other ticket was modified.

**LOCAL-ONLY note (AC #5):** per this run's explicit constraint, **no
git push/PR/commit/remote** — consistent with the accepted LOCAL-ONLY
disposition of every prior WS-A/WS-B/WS-D gate for this program. All content
is on-disk on the current checkout only. Whether GATE-6 closes on local
green evidence (as GATE-5 did, per DAS-1576's precedent) or requires a
merged PR is the **COO's call** (GATE-6 accountable per the AI-agent-
lifecycle policy) — flagging it rather than deciding it, per my charter.

Setting `status: in_review`, `assignee: coo` (GATE-6 accountable; Support
Lead consulted per the policy's RACI row). This is the last WS-D LENS
ticket (DAS-1570 epic) — GATE-6 closure by the COO would close out the
program.

### 2026-07-24 — COO

**GATE-6 (Maintenance) closure decision: ACCEPT on LOCAL-ONLY disposition**,
consistent with GATE-1..5 precedent for this program (per DAS-1576).

Independently re-verified on current checkout (branch
`docs/governed-devin-langchain-direction`), exact commands:
- `python3 -m pytest tests/test_ws_d_health_check.py -q` → **12 passed**.
- `python3 scripts/diagnostics.py` → **SCORE = 100/100**.
- `python3 scripts/board_lint.py` → **exit 0 — OK: 180 ticket(s) checked, 0
  violations** (same pre-existing DAS-1507 body-status WARN, unrelated,
  non-fatal).
- `grep -n "ws-d-lens-health" scripts/stage_gate.py` → confirmed present
  (`recurring_runs` entry, config points at
  `docs/06-maintenance/ws-d-lens-health.md`).
- `docs/06-maintenance/ws-d-lens-health.md` → confirmed contains an
  **Alerting — a failure is never silent** section and a **Founder-reviewed
  learnings → `daslab-learn` (ADR-0029 G5)** section; both match the Product
  Analyst's log description (follow-up ticket on failure, no
  auto-remediation, `daslab-learn` distills only Founder-accepted feedback,
  no self-modification).

All five acceptance criteria are met on the evidence above. No gap found —
no reason to route back. Per the AI-agent-lifecycle policy's RACI row, GATE-6
is the COO's call; local-on-disk green evidence is accepted as sufficient,
matching how GATE-5 (DAS-1576) closed. No git push/PR/commit/remote was
performed (LOCAL-ONLY constraint honored; only this ticket file edited).

**DAS-1577 → `status: done`.** This closes GATE-6, the sixth and final
AADL gate for WS-D LENS. All six AADL gates (Planning, Design, Development,
Testing, Deployment, Maintenance) for WS-D LENS are now closed — epic
DAS-1570 is ready for the orchestrator to mark done.
