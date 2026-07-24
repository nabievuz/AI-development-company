---
id: DAS-1601
title: WS-H Development — Founder-only approve-gate and WS-B trigger-run endpoints through the board
status: backlog
assignee: cto
author: ceo
dept: engineering
priority: p1
parent: DAS-1597
goal: mustaqil-ws-h-control
spec: 008-mustaqil-ws-h-control
implements: [FR-003, FR-004, FR-005]
labels: [security]
zone: tools/control_plane
depends_on: [DAS-1600]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 3 — Development (closes GATE-3 for WS-H, part 2).** Add the two remaining
governed write classes on top of the DAS-1600 hardened core. Security Lead consulted —
this is the QONUN-5 approval surface. Sequenced on DAS-1600 (same `tools/control_plane`
zone: both extend `app.py`), so the two Development tickets do not collide in one wave.

- **CP-3c approve-gate (FR-004/Q6):** an endpoint to approve/deny a gate or
  interrupt-card, bound to a **Founder-role identity** via RBAC. The dashboard, an agent,
  or any non-Founder role (viewer/operator) **cannot** sign a gate — a non-Founder
  attempt is refused with an audited deny. Bind to the **real** gate/interrupt-card
  machinery (`board/interrupts/`, the AADL gate path) — never a PoC stub. A GATE-5-open
  deployment stays **machine-blocked** regardless of any button (never-auto-approve).
- **CP-3b trigger-run (FR-003):** an endpoint to trigger a run via the **WS-B headless
  runner** (ADR-0034). RBAC-authorized (operator+), it orchestrates the existing runner
  entrypoint — it does not re-implement dispatch; the server itself dispatches nothing
  (CP-5). Requires the WS-B runner to be landed (sequence precondition, DAS-1598).
- **CP-4 board-canonical (FR-005):** both writes go **through** the canonical board /
  interrupt-cards / event store — no parallel dashboard state; a divergence resolves to
  the board. Every request/decision is appended to the audit trail, redacted (ADR-0012).

Feature-flagged OFF (`ws_h_control_plane`); with the flag OFF the endpoints are inert
and dispatch is byte-identical to pre-merge.

## Acceptance criteria
- [ ] Approve-gate endpoint binds to a Founder-role identity; a non-Founder (viewer/operator/agent/dashboard) approval is refused with an audited deny (FR-004); bound to the real gate/interrupt-card machinery, not a stub.
- [ ] A GATE-5-open deployment stays machine-blocked regardless of any dashboard action (never-auto-approve / QONUN-5).
- [ ] Trigger-run endpoint invokes the WS-B headless runner (ADR-0034) through its existing entrypoint; the server re-implements no dispatch and dispatches nothing on its own (FR-003/CP-5).
- [ ] Both writes go through the canonical board/interrupt-cards/event store (FR-005/CP-4); each is audited + redacted (ADR-0012).
- [ ] Feature-flagged OFF; flag-off behaviour byte-identical to pre-merge. `diagnostics.py` 100/100; validators green. Merged PR, green CI. Security Lead review recorded.

## Log
### 2026-07-24 — CEO
Created by /daslab-plan (WS-H Development, part 2). CP-3c Founder-only approve-gate
(bound to the real gate machinery, not a stub) + CP-3b WS-B trigger-run, both through
the board (CP-4). Sequenced on DAS-1600 (same app.py zone). Security Lead consulted.
