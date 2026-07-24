---
id: DAS-1598
title: WS-H Planning — ratify ADR-0039, review SPEC-008, confirm the WS-H feature key OFF
status: backlog
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
