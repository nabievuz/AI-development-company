---
id: DAS-1597
title: MUSTAQIL WS-H CONTROL — self-hosted web control plane over the cockpit (EPIC)
status: done
assignee: cto
author: ceo
dept: engineering
priority: p1
parent: 
goal: mustaqil-ws-h-control
spec: 008-mustaqil-ws-h-control
labels: [security]
depends_on: [DAS-1543]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**EPIC — MUSTAQIL v3.0 WS-H CONTROL.** Extend the read-only operator cockpit
(ADR-0028 `cockpit_html`) into a self-hosted **web control plane** — operate DasLab
from a browser on the tenant's own Ubuntu (Linux-first) or macOS server: see the board
and the real cockpit, submit a goal, trigger a run, approve/deny a gate — while every
write stays **Founder-only RBAC-gated, audited, redacted, and gate-bounded**. Control
goes **up** without governance going **down**.

**Contract of record:** ADR-0039 (CP-1…CP-6), `docs/specs/008-mustaqil-ws-h-control/SPEC.md`
(FR-001…FR-008, SC-001…SC-005), master-prompt v3.0 row H + Part 0 (WS-H deployment
reality: offline-install + NOT-a-daemon), Founder discovery Q6 (Founder-only approval;
read-only audit for a small team).

**Extend-vs-new (do not duplicate).** Fold in the on-branch spike rather than rebuild:
`tools/control_plane/app.py` (FastAPI PoC: RBAC viewer<operator<founder, board read,
real cockpit embed, audit tail, CP-3a goal-proposal write), its
`requirements-control.txt`, `tests/test_ws_h_control_plane.py` (7 tests), and the
runbook `docs/runbooks/ws-h-control-plane.md`. These are spikes ahead of formal
tickets — harden and merge them; a spike is not a delivery until it passes in CI under
a merged ticket (ADR-0020). **NOTE:** `tools/control_plane/app.py` currently carries
**10 ruff B008 violations** (`Depends(require(...))` in argument defaults) that the
Development stage MUST clean.

**Sequence (master-prompt v3.0):** WS-H runs **after WS-B (0034 runner) + WS-D (0036
lens) + WS-E (0038 tenant hardening)** — it needs the headless runner to trigger a run,
the self-host lens for live status, and the in-tenant RBAC/secrets boundary. A
workstream may not skip its predecessor's AADL gate. On the board today only the WS-A
tickets (DAS-1544…1551) and the prep bootstraps (DAS-1541…1543) are materialized;
WS-B/WS-D/WS-E tickets are not yet minted, so this epic's runtime predecessors are
enforced by the sequence note, not yet by a `depends_on` edge (which would dangle). The
epic depends only on the program bootstrap DAS-1543 (feature-flag scaffold), like WS-A.

**Cross-reference — WS-G PROOF (ADR-0037).** This workstream is the **WS-G proof-project
target**: discovery Q1's default proof is to dogfood the WS-H dashboard's next slice, so
building the control plane 0→100 through the six AADL gates on self-host infra is also
the first end-to-end proof. WS-G's "shipped" evidence (Q7: merged + green CI + deployed
to the tenant VM) is expected to be demonstrated on this dashboard slice.

**AADL — six-stage closure (children DAS-1598..DAS-1605):**

| Child | Stage | Ticket | Owner-hint |
|---|---|---|---|
| DAS-1598 | Planning | Ratify ADR-0039 + review SPEC-008 + confirm the WS-H feature key OFF | cto |
| DAS-1599 | Design | Control-plane design — Founder-only RBAC + audit (CP-2/3/Q6), approve-gate + trigger-run UX, offline-install + NOT-a-daemon/degrade-to-static | backend-em |
| DAS-1600 | Development | Harden control_plane/app.py incl the 10-error ruff cleanup, Founder-only RBAC + audit, render-seam reuse (CP-1) | backend-em |
| DAS-1601 | Development | Approve-gate (CP-3c, Founder-identity) + trigger-run (CP-3b, WS-B runner) endpoints, through the board (CP-4) | backend-eng-1 |
| DAS-1602 | Development | Vendored-wheels offline install (FR-008) + degrade-to-static + optional Founder-enabled process (CP-5/6) | sre-eng |
| DAS-1603 | Testing | Negative tests — RBAC deny/fail-closed, Founder-only approval, audit, offline-install boot | qa-eng |
| DAS-1604 | Deployment | Runbook + flag stays OFF on merge, systemd/launchd opt-in, degrade-to-static default | sre-eng |
| DAS-1605 | Maintenance | Scheduled health/eval of the control edge (RBAC drift, audit-redaction probe) | product-analyst |

## Acceptance criteria
- [ ] All eight children (DAS-1598..DAS-1605) closed, each through its own AADL stage gate.
- [ ] **FR-001/CP-1:** the control plane extends the ADR-0028 cockpit through its single render seam; no second cockpit is forked; the read cockpit remains the degrade-to-static base.
- [ ] **FR-002/CP-2:** every data/action endpoint is RBAC-identified with no anonymous access; unconfigured RBAC fails closed (503) — a negative test proves it (SC-001) — and it serves only in-tenant.
- [ ] **FR-003/CP-3:** exactly three governed write classes (goal proposal / trigger run / approve-deny gate), each RBAC-authorized and each audited + redacted (ADR-0012).
- [ ] **FR-004/CP-3 + Q6:** gate approval binds to a Founder-role identity; a non-Founder (viewer/operator/agent/dashboard) is refused; a GATE-5-open deployment stays machine-blocked — a negative test proves it (SC-002).
- [ ] **FR-005/CP-4:** all reads/writes go through the canonical board/queue/event-store; no parallel dashboard state; a divergence resolves to the board.
- [ ] **FR-006/CP-5:** optional, Founder-enabled, feature-flagged OFF, degrades to static, dispatches nothing on its own — flag-OFF dispatch byte-identical to pre-merge (SC-004).
- [ ] **FR-007/CP-6:** in-tenant only, no external SaaS, secrets in the tenant vault.
- [ ] **FR-008:** offline-installable from a vendored wheel bundle — an install test proves offline boot (SC-003).
- [ ] On-branch spike (`tools/control_plane/app.py` + tests + runbook) folded in and passing in CI (not left as an untracked prototype); the 10 ruff B008 violations cleaned.
- [ ] `diagnostics.py` 100/100; `board_lint`/`check_spec_consistency`/`check_dependency_graph`/validators green; no `project:` field on any WS-H ticket (R9); committed wave attestation (ADR-0031/0032).
- [ ] **Epic acceptance = AADL 6-gate closure for WS-H**, each gate logged in the stage-board; doubles as the WS-G PROOF slice (ADR-0037).

## Log
### 2026-07-24 — CEO
Created by /daslab-plan from the Founder-approved MUSTAQIL v3.0 queue (WS-H CONTROL).
Contract = ADR-0039 (CP-1..CP-6) + SPEC-008 (FR-001..FR-008, SC-001..SC-005). Children
DAS-1598..DAS-1605 (one per AADL stage, 3 Development). Sequenced after WS-B+WS-D+WS-E
(sequence note; not a `depends_on` edge — those tickets are not yet on the board).
Folds in the on-branch `tools/control_plane/app.py` spike (10 ruff B008 to clean).
Cross-referenced as the WS-G proof-project target. Org-engine epic — no `project:` field
(board_lint R9). Depends on the program bootstrap DAS-1543 (feature-flag scaffold;
`ws_h_control_plane: false` already present in config/features.yaml).

### 2026-07-25 — Orchestrator (/daslab-cycle)
**EPIC CLOSED — WS-H CONTROL complete.** All six AADL gates: GATE-1 (1598 ADR-0039) → GATE-2 (1599 design, RBAC-SSOT + not-a-daemon) → GATE-3 (1600 harden app + RBAC/audit [B008 spike debt cleaned], 1601 approve-gate/trigger-run [Founder-only event, GATE-5-open stays blocked], 1602 offline-install + degrade-static; security-eng red-team PASSED — QONUN-5 web approval boundary structurally sound; R1 constant-time token + R3 CI-theatre [endpoint tests now actually run in CI] fixed) → GATE-4 (1603 negatives + R1..R4, 0 xfailed) → GATE-5 (1604 offline-install runbook, flag OFF) → GATE-6 (1605 RBAC/audit/degrade/token drift health). Behind ws_h_control_plane OFF; degrades to the ADR-0028 static cockpit. LOCAL-ONLY. Unblocks A2A (1606, deferred until after proof per Q12) + WS-F TEMPO (1615, LAST).
