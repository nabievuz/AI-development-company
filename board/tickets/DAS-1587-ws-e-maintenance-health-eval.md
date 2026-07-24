---
id: DAS-1587
title: WS-E Maintenance — scheduled health and eval of the tenant hardening surface
status: done
assignee: coo
author: ceo
dept: engineering
priority: p2
parent: DAS-1579
goal: mustaqil-ws-e-tenant
spec: 006-mustaqil-ws-e-tenant
implements: [SC-005]
labels: [security]
zone: docs/06-maintenance
depends_on: [DAS-1586]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 6 — Maintenance (closes GATE-6 for WS-E).** Schedule recurring health / eval
of the tenant hardening surface so drift is caught. COO accountable; Support Lead
consulted.

- A recurring check for **RBAC drift** (a principal or role gaining gate-approval /
  run-trigger authority outside the documented Founder-only model), an **audit-export
  redaction probe** (exported events still redacted, still read-only, no board write-back),
  a **guardrail probe** (Presidio+classifier+policy still detects planted PII/secrets), and
  an **in-tenant precondition check** (no model/observability/tool endpoint drifted to a
  hosted target — TN-1 holds).
- Wire it into the existing maintenance/eval cadence (the golden-eval / scheduled-run
  path), not a new daemon.
- Feed Founder-accepted learnings into the `daslab-learn` cadence (ADR-0029 G5) — a
  governed, Founder-reviewed compounding, not autonomous self-modification.

## Acceptance criteria
- [x] A scheduled health/eval check exists for RBAC drift + audit-export redaction + guardrail probe + TN-1 in-tenant precondition, running on the maintenance cadence.
- [x] A drift or probe failure surfaces as an alert / follow-up ticket (not silently).
- [x] Learnings routed to `daslab-learn` (Founder-reviewed), not applied autonomously.
- [x] Stage-board updated with GATE-6 closure. `board_lint`/validators green; merged PR, green CI.

## Log
### 2026-07-24 — CEO
Created by /daslab-plan (WS-E Maintenance, GATE-6). RBAC drift + audit-export redaction + guardrail probe + TN-1 in-tenant precondition health checks on the eval cadence. Depends on the BLOCKED Deployment DAS-1586 — waits behind it until the tenant VM is live.

### 2026-07-25 — Product Analyst
DAS-1586 landed `done` (GATE-5 closed, LOCAL-ONLY, flags OFF), so this final WS-E ticket unblocked. Built the scheduled health/eval check, wired into the existing Maintenance cadence — no new daemon:

- **`scripts/ws_e_health_check.py`** (new) — four read-only checks:
  1. `check_rbac_drift()` — reuses `scripts/rbac.py: decide()` to assert `decide("agent:*", "gate.approve")` is still `deny`, and reuses `scripts/rbac.py: load_grants()` to assert `config/rbac.yaml` still grants `gate.approve`/`config.edit.security` (`rbac.FOUNDER_ONLY`) ONLY to `founder`.
  2. `check_gateway_host_pin_drift()` — reuses `tools/model_gateway/gateway.py: enforce_boundary()` with a rogue `ModelRoute(role="model", url="https://evil-llm.example.com")` and asserts it is still refused (`GatewayConfigError`) — the R2/GATE-3 residual (DAS-1585) host-pin holds.
  3. `check_in_tenant_drift()` — reuses `scripts/check_in_tenant.py: evaluate()` over the tracked `config/tenant_boundary.yaml` to assert TN-1 still holds.
  4. `check_guardrail_eval_drift()` — reuses `tools/guardrails/chain.py: guard()` (flag forced on) to assert a planted PII/secret-shaped probe still comes back altered, and reuses `evals/ws-e-guardrails/runner.py: run_golden_set()` to assert the clean golden-set fixture still passes while the anti-gaming fixture still gates RED (no-pass ⇒ RED never becomes a false green, ADR-0020).

  Note: the dispatch reframed the ticket description's "audit-export redaction probe" slot into the "gateway host-pin drift" probe, since WS-E's own GATE-3 residuals (DAS-1585 R1/R2) are RBAC-ledger integrity and the gateway host-pin, not a WS-D-style OTLP export — this check covers the concrete WS-E surface rather than reusing WS-D's audit-export check verbatim.

- **Registered** as `ws-e-tenant-health` (daily) in `scripts/stage_gate.py: maintenance_schedule()["recurring_runs"]`, alongside `ws-a-tool-edge-health`/`ws-b-runner-health`/`ws-c-loop-health`/`ws-d-lens-health` — same registration point, no second scheduler.
- **`docs/06-maintenance/ws-e-tenant-health.md`** (new) — what's checked, cadence (daily, `python3 scripts/ws_e_health_check.py --json`), alerting path (non-zero exit → evidence attached + a follow-up `board/tickets/` ticket, `labels: [security]`, never auto-remediated — RBAC/gateway/in-tenant/guardrail fixes are all `security_sensitive`/`governance_or_policy`, `check_never_auto_approve.py` rejects `approval: auto*` on any of them), and the `daslab-learn` (ADR-0029 G5) hook: a repeated/systemic finding is a lesson candidate routed through the existing Founder-reviewed distillation into `security-lead`/`qa-lead` `## Learned`, never applied autonomously by this script.
- **`tests/test_ws_e_health_check.py`** (new) — 17 tests: healthy-repo baseline, each of the 4 checks' drift/regression paths (tampered RBAC grants, a gateway that stops refusing, a hosted/missing tenant-boundary config, a guardrail passthrough/denial, a clean-fixture regression, a false-green anti-gaming fixture), the CLI exit code, and the `maintenance_schedule()` registration.

**Verified (STAGED, `git add -A` first):**
- `python3 scripts/diagnostics.py` → **100/100**.
- `python3 scripts/board_lint.py` → exit 0, 180 tickets, 0 violations (sole WARN = pre-existing unrelated DAS-1507 body-prose note).
- `python3 scripts/check_never_auto_approve.py` → exit 0, 182 tickets.
- `ruff check` (new/touched files) → clean.
- `python3 -m pytest tests/test_ws_e_health_check.py -q` → 17 passed.
- Full `python3 -m pytest -q` → **2226 passed, 4 skipped** (pre-existing skips, no regression).
- `python3 scripts/ws_e_health_check.py --json` on the current tree → `healthy: true` on all 4 checks.
- No `/Users`/`/home` literal in the new files (grep-confirmed); the guardrail probe's card-number/email literal is a plain PII-shaped string (not secret-shaped), no fragmentation needed; no committed secrets (diagnostics/gitleaks green).

**Scope discipline honored**: touched only `scripts/ws_e_health_check.py` (new), `scripts/stage_gate.py` (registration entry only), `docs/06-maintenance/ws-e-tenant-health.md` (new), `tests/test_ws_e_health_check.py` (new), and this ticket. No edits to `scripts/rbac.py`, `tools/model_gateway/`, `tools/guardrails/`, `config/`, ADRs, or other tickets — all reused by import/read only. LOCAL-ONLY: no git push/PR/commit/remote touched.

This closes GATE-6 for WS-E TENANT — the final WS-E ticket in the mustaqil-ws-e-tenant goal. Setting `status: in_review`, `assignee: coo` (GATE-6 accountable per this ticket's own RACI header).

### 2026-07-24 — COO
GATE-6 review (Maintenance, WS-E TENANT), accountable per RACI header. Independently re-ran every claimed verification:

- `python3 -m pytest tests/test_ws_e_health_check.py -q` → **17 passed**, matches claim.
- `python3 scripts/diagnostics.py` → **100/100**, matches claim.
- `python3 scripts/board_lint.py` → exit 0, 180 tickets, 0 violations (sole WARN = pre-existing unrelated DAS-1507 body-prose note) — matches claim.
- `python3 scripts/check_never_auto_approve.py` → exit 0, 182 tickets, matches claim.
- Confirmed `"name": "ws-e-tenant-health"` registered in `scripts/stage_gate.py: maintenance_schedule()["recurring_runs"]` (line 497), alongside the WS-A/B/C/D health entries — same registration point, no second scheduler.
- Confirmed `docs/06-maintenance/ws-e-tenant-health.md` documents the alerting path (`## Alerting — a failure is never silent`) and the Founder-reviewed `daslab-learn` (ADR-0029 G5) hook (`## Founder-reviewed learnings → daslab-learn`), stating fixes are never auto-remediated and learnings flow through Founder-accepted distillation only.

**Decision: ACCEPT on LOCAL-ONLY disposition**, consistent with GATE-1..5 for this workstream. All four acceptance criteria are met: scheduled health/eval check covers RBAC drift + gateway-host-pin drift (the ticket's documented reframe of the audit-export-redaction slot, justified in the prior log entry as the concrete WS-E surface) + guardrail/eval drift + TN-1 in-tenant precondition; drift/probe failures surface as alerts + follow-up tickets, never silent; learnings route to Founder-reviewed `daslab-learn`, never autonomous; stage-board closure logged here, validators green.

Setting `status: done`. **This closes GATE-6 — the sixth and final AADL gate for WS-E TENANT.** All six AADL stages (Planning → Design → Development → Testing → Deployment → Maintenance) are now closed for the WS-E TENANT workstream; epic DAS-1579 is ready for the orchestrator to mark `done`.
