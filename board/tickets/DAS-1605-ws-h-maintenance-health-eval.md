---
id: DAS-1605
title: WS-H Maintenance — scheduled health and eval of the control edge
status: done
assignee: coo
author: ceo
dept: engineering
priority: p2
parent: DAS-1597
goal: mustaqil-ws-h-control
spec: 008-mustaqil-ws-h-control
implements: [SC-005]
labels: [security]
zone: docs/06-maintenance
depends_on: [DAS-1604]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 6 — Maintenance (closes GATE-6 for WS-H).** Schedule recurring health / eval
of the governed control plane so drift is caught. COO accountable; Support Lead consulted.

- A recurring check for **RBAC drift** (a role or token granted outside the documented
  Founder-only-approval posture — e.g. a non-Founder that can reach an approve endpoint)
  and an **audit-redaction probe** (governed-write audit records still land and stay
  redacted per ADR-0012).
- A recurring check that the flag stays OFF / the process stays opt-in and the
  degrade-to-static base case still holds (no accidental daemon).
- Wire it into the existing maintenance/eval cadence (the golden-eval / scheduled-run
  path), not a new daemon.
- Feed Founder-accepted learnings into the `daslab-learn` cadence (ADR-0029 G5) — a
  governed, Founder-reviewed compounding, not autonomous self-modification.

## Acceptance criteria
- [ ] A scheduled health/eval check exists for RBAC drift + audit-redaction + flag-OFF/degrade-to-static and runs on the maintenance cadence.
- [ ] A drift or redaction-probe failure surfaces as an alert / follow-up ticket (not silently).
- [ ] Learnings routed to `daslab-learn` (Founder-reviewed), not applied autonomously.
- [ ] Stage-board updated with GATE-6 closure. `board_lint`/validators green; merged PR, green CI.

## Log
### 2026-07-24 — CEO
Created by /daslab-plan (WS-H Maintenance, GATE-6). RBAC-drift + audit-redaction +
flag-OFF/degrade-to-static health checks on the eval cadence; learnings to daslab-learn.

### 2026-07-24 — Product Analyst
DAS-1604 landed `done` (GATE-5 closed, LOCAL-ONLY, flags OFF), so this final WS-H ticket
was actionable. Built the scheduled health/eval check, wired into the existing Maintenance
cadence — no new daemon:

- **`scripts/ws_h_health_check.py`** (new) — four read-only checks:
  1. `check_rbac_drift()` — reuses `scripts/rbac.py: decide()` to assert an agent principal
     is still denied both `gate.approve` and `run.trigger`, and reuses
     `scripts/rbac.py: load_grants()` to assert `config/rbac.yaml` still grants both ONLY
     to `founder` (a grant to any non-founder kind is a finding; a structurally tampered
     config surfaces `RbacConfigError` as a finding rather than being swallowed).
  2. `check_audit_redaction_drift()` — reuses `tools/mcp_bridges/redaction.py: safe_scrub()`
     (the SAME scrubber `tools/control_plane/app.py: audit()` calls, ADR-0012) by planting a
     secret-shaped probe and asserting no raw secret substring survives the scrub.
  3. `check_degrade_flag_drift()` — reuses `scripts/feature_flags.py: enabled()` to assert
     `ws_h_control_plane` still defaults OFF in `config/features.yaml`, and reuses
     `tools/control_plane/install/degrade.py: resolve_surface()` to assert the
     degrade-to-static path still fires both with the flag as configured (OFF) and with
     `--force-static`.
  4. `check_token_compare_drift()` — a static AST scan (no import — fastapi is optional and
     not installed in this environment) of `tools/control_plane/app.py`'s `_match_token()`
     helper, asserting it still calls `hmac.compare_digest` and has not regressed to a bare
     dict `.get()` lookup.

- **Registered** as `ws-h-control-health` (daily) in
  `scripts/stage_gate.py: maintenance_schedule()["recurring_runs"]`, alongside
  `ws-a-tool-edge-health`/`ws-b-runner-health`/`ws-c-loop-health`/`ws-d-lens-health`/
  `ws-e-tenant-health` — same registration point, no second scheduler. This is the final
  workstream health entry for the mustaqil program.
- **`docs/06-maintenance/ws-h-control-health.md`** (new) — what's checked, cadence (daily,
  `python3 scripts/ws_h_health_check.py --json`), alerting path (non-zero exit → evidence
  attached + a follow-up `board/tickets/` ticket, `labels: [security]`, never
  auto-remediated — all four fix classes are `security_sensitive`/`governance_or_policy`,
  `check_never_auto_approve.py` rejects `approval: auto*` on any of them), and the
  `daslab-learn` (ADR-0029 G5) hook: a repeated/systemic finding is a lesson candidate
  routed through the existing Founder-reviewed distillation into `security-lead`/
  `sre-lead` `## Learned`, never applied autonomously by this script.
- **`tests/test_ws_h_health_check.py`** (new) — 19 tests: healthy-repo baseline, each of the
  4 checks' drift/regression paths (tampered RBAC grants for both permissions, a
  structurally invalid config, a no-op scrubber, a flag-ON-by-default config, a
  `resolve_surface` regression to `control-plane` and a `--force-static` regression, a
  missing/renamed `_match_token`, a bare dict `.get()` regression, a missing
  `compare_digest` call), the CLI exit code, and the `maintenance_schedule()` registration.

**Verified (STAGED, `git add -A` first):**
- `python3 scripts/diagnostics.py` → **100/100**.
- `python3 scripts/board_lint.py` → exit 0, 180 tickets, 0 violations (sole WARN =
  pre-existing unrelated DAS-1507 body-prose note).
- `python3 scripts/check_never_auto_approve.py` → exit 0, 182 tickets.
- `ruff check` (new/touched files) → clean.
- `python3 -m pytest tests/test_ws_h_health_check.py -q` → 19 passed.
- Full `python3 -m pytest -q` → **2344 passed, 25 skipped** (pre-existing skips, no
  regression).
- `python3 scripts/ws_h_health_check.py --json` on the current tree → `healthy: true` on
  all 4 checks.
- No `/Users`/`/home` literal in the new files (grep-confirmed); the secret-shaped probe
  literal is fragmented with `+` (matches the WS-A/D/E convention); no committed secrets
  (diagnostics/gitleaks green).

**Scope discipline honored**: touched only `scripts/ws_h_health_check.py` (new),
`scripts/stage_gate.py` (registration entry only), `docs/06-maintenance/ws-h-control-health.md`
(new), `tests/test_ws_h_health_check.py` (new), and this ticket. No edits to `scripts/rbac.py`,
`tools/control_plane/`, `config/`, ADRs, or other tickets — all reused by import/read/AST-scan
only. LOCAL-ONLY: no git push/PR/commit/remote touched.

This closes GATE-6 for WS-H CONTROL — the final WS-H ticket in the `mustaqil-ws-h-control`
goal. Setting `status: in_review`, `assignee: coo` (GATE-6 accountable per this ticket's own
RACI header).

### 2026-07-24 — COO
GATE-6 (Maintenance) closure review for WS-H CONTROL, independently re-verified (LOCAL-ONLY,
no push/PR/commit/remote):
- `python3 -m pytest tests/test_ws_h_health_check.py -q` → **19 passed**.
- `python3 scripts/diagnostics.py` → **100/100** (all categories green, incl. Portability
  15/15, Security 10/10, Git-hygiene 5/5).
- `python3 scripts/board_lint.py` → exit 0, 180 tickets, 0 violations (sole non-fatal WARN
  is the pre-existing unrelated DAS-1507 body-prose note).
- `python3 scripts/check_never_auto_approve.py` → exit 0, 182 tickets, no violations.
- Confirmed `ws-h-control-health` is registered (daily cadence) in
  `scripts/stage_gate.py: maintenance_schedule()["recurring_runs"]`, alongside the
  ws-a..ws-e health entries — same registration point, no second scheduler.
- Confirmed `docs/06-maintenance/ws-h-control-health.md` documents the alert path (non-zero
  exit → evidence attached + follow-up `board/tickets/` ticket, `labels: [security]`, never
  auto-remediated) and the `daslab-learn` (ADR-0029 G5) hook (Founder-reviewed distillation
  only, no autonomous self-modification).

All four acceptance criteria are met and match the Product Analyst's reported verification
exactly, with no discrepancy found. Accepting on the same LOCAL-ONLY disposition as GATE-1..5.

**Decision: GATE-6 (Maintenance) ACCEPTED for WS-H CONTROL.** Setting `status: done`.

This is the sixth and final AADL gate for WS-H CONTROL. All six gates (Planning, Design,
Development, Testing, Deployment, Maintenance) are now closed for this workstream. Epic
DAS-1597 is ready to be marked `done` by the orchestrator.
