---
id: DAS-1598
title: WS-H Planning — ratify ADR-0039, review SPEC-008, confirm the WS-H feature key OFF
status: done
assignee: cto
author: ceo
dept: engineering
priority: p1
parent: DAS-1597
goal: mustaqil-ws-h-control
spec: 008-mustaqil-ws-h-control
implements: [FR-001, FR-006]
labels: [governance, security]
zone: docs/adr
depends_on: [DAS-1543]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 1 — Planning (closes GATE-1 for WS-H).**

- Ratify **ADR-0039** (currently `Proposed`) → `Accepted` after CTO sign-off (RACI
  3.1/3.6); Security Lead consulted on auth/RBAC/audit; CDO consulted on dashboard UX.
- Review `docs/specs/008-mustaqil-ws-h-control/SPEC.md` (FR-001…FR-008, SC-001…SC-005);
  resolve any `[NEEDS CLARIFICATION]`; mark SPEC Status `reviewed`.
- Confirm the WS-H feature key in `config/features.yaml` DEFAULT **OFF**
  (`ws_h_control_plane: false`, already landed by the DAS-1543 scaffold) — the flag that
  guards the optional control-plane process (CP-5/FR-006). Confirm only; do not re-add.
- Confirm the sequence precondition on record: WS-H builds against WS-B (0034 runner,
  for trigger-run CP-3b) + WS-D (0036 lens, for live status) + WS-E (0038, for the
  in-tenant RBAC/secrets boundary). No WS-H code stage may open before those gates.

No control-plane code is built in this stage — this fixes the contract the WS-H code
builds against.

## Acceptance criteria
- [ ] ADR-0039 Status flipped to `Accepted` with the CTO sign-off recorded; `docs/adr/README.md` consistent; Security Lead (auth/RBAC/audit) + CDO (UX) consult captured.
- [ ] SPEC-008 reviewed (Status `reviewed`), no unresolved clarification markers; FR/SC ids each defined exactly once (check_spec_consistency structural check).
- [ ] WS-H feature key confirmed present in `config/features.yaml`, value `false`, with a consumer/flip comment (confirmed from DAS-1543 — not re-added).
- [ ] Sequence precondition (after WS-B+WS-D+WS-E) recorded in the stage-board.
- [ ] `check_spec_consistency`/`check_links`/`board_lint`/`check_dependency_graph` green. (Doc/governance ticket, LOCAL-ONLY — no PR/CI exists; exempt from the merged-PR done-gate, accepted on local green.)

## Log
### 2026-07-24 — CEO
Created by /daslab-plan (WS-H Planning). Ratifies ADR-0039; reviews SPEC-008; confirms
the `ws_h_control_plane` flag OFF and the after-WS-B+D+E sequence precondition. GATE-1
unblocks the WS-H Design ticket DAS-1599.

### 2026-07-24 — CTO (GATE-1 Planning closure)
**AADL Stage-1 (Planning) closed for WS-H CONTROL.** Verdict: **ADR-0039 ratified
Proposed → Accepted** — architecturally sound on all four judged axes:

- **Founder-only RBAC + audit (CP-3/FR-004).** Verified against the WS-E RBAC SSOT
  (`config/rbac.yaml` / `scripts/rbac.py`) the ADR mandates reusing: `gate.approve` is a
  Founder-identity permission, structurally founder-only — `load_grants` refuses any
  file granting it to a non-founder kind, and `decide("agent:<role>", "gate.approve")`
  == deny by construction. The dashboard, an agent, or any non-Founder role can NEVER
  sign a gate; every write appends to the event store (0024/0025), redacted (0012).
  Matches Founder Q6 ("Founder-only + team read"). No path to a gate approval without a
  Founder identity — the escalated defect class does not exist here.
- **NOT-a-daemon / degrade-to-static (CP-5/FR-006).** Optional, Founder-enabled,
  feature-flagged-OFF process; degrades to the ADR-0028 static read cockpit; dispatches
  nothing on its own (a wave advances only from a human write or the HEARTBEAT). The
  runbook confirms loopback-default bind + degrade-to-static base. It CAN degrade to
  static — the escalated daemon-defect class does not exist here.
- **Offline-installable (CP-6/FR-008).** In-tenant only, no external SaaS; vendored wheel
  bundle installs + boots with no network (verified on-device: fastapi/uvicorn/starlette/
  pydantic import clean, `/healthz` 200, arm64/cp310).
- **Board-canonical + never-bypass-a-gate (CP-4/C2, C4).** All reads+writes route through
  `board/tickets/`, the goal queue, and the event store; a GATE-5-open deployment stays
  machine-blocked regardless of any button.

**Review finding (recorded, not a defect — safe by fail-closed).** SPEC P2 scenario and
the on-branch spike `tools/control_plane/app.py` use an ad-hoc `viewer<operator<founder`
tier where a non-Founder "operator" triggers runs. The WS-E RBAC SSOT WS-H MUST reuse has
NO operator kind (kinds: founder / audit-team / agent / orchestrator) and makes
`run.trigger` **Founder-only**, audit-team read-only. The SSOT is strictly more
restrictive and fail-closed, so nothing unsafe passes; I reworded the SPEC P2 scenario to
the SSOT model and recorded a **binding constraint on Design/Development**: bind writes to
`scripts/rbac.py` (the SSOT), NOT the spike's tier.

**SPEC-008 reviewed** (draft → reviewed): every FR/SC coherent, testable, traceable to
ADR-0039 CP-1…CP-6; no unresolved clarification marker. (Reworded P2 for SSOT coherence;
no FR-/SC- id token added.)

**Feature key confirmed** (not re-added): `config/features.yaml:27` `ws_h_control_plane:
false` with consumer/flip comment (landed by DAS-1543). **Sequence precondition on
record:** WS-H builds after WS-B (0034 runner, trigger-run) + WS-D (0036 lens, live
status) + WS-E (0038 RBAC/secrets) — all `done`; no WS-H code stage opens before them.

**Development-hardening note (routed to DAS-1599/Dev):** the spike's ~10 B008 ruff
violations in `tools/control_plane/app.py` (FastAPI `Depends`/`require` in argument
defaults) must be cleaned as part of hardening it (also SC-005).

**Changed:** `docs/adr/0039-self-hosted-web-control-plane.md` (Status → Accepted + CTO
sign-off), `docs/adr/README.md` (row 0039 → Accepted), `docs/specs/008-mustaqil-ws-h-control/SPEC.md`
(Status → reviewed + P2 SSOT-coherence rewording + CTO review notes), this ticket.

**Validators (LOCAL-ONLY, no PR/CI):** `check_spec_consistency` exit 0 (10 SPECs),
`check_links` exit 0, `board_lint` exit 0 (180 tickets, 0 violations),
`check_dependency_graph` exit 0. Doc/governance ticket — exempt from the merged-PR
done-gate per acceptance criteria, accepted on local green.

Consults captured in ADR-0039 (Security Lead — auth/RBAC/audit; CDO — dashboard UX).
**GATE-1 closed → unblocks DAS-1599 (WS-H Design).**
