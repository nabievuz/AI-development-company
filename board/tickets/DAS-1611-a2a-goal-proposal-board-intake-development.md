---
id: DAS-1611
title: A2A Development — goal-proposal to board intake, never an approval
status: backlog
assignee: backend-eng-1
author: ceo
dept: engineering
priority: p1
parent: DAS-1606
goal: mustaqil-a2a-outbound
spec: 009-mustaqil-a2a-outbound
implements: [FR-002]
labels: [security]
zone: scripts/a2a_intake
depends_on: [DAS-1608, DAS-1609]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 3 — Development (part B of GATE-3 for A2A OUTBOUND).**

Build the goal-proposal intake path per the DAS-1608 design:

- Implement the intake handler that takes an external caller's goal-proposal
  submission (shape per DAS-1608) and writes it ONLY as a board-intake artifact
  — landing ahead of / into the existing Founder-Approved Goal Queue mechanism,
  never as a ticket that starts `todo`/`in_progress`, and never touching an
  `approval`/gate-status/routing field (C3, QONUN-5).
- Implement the refusal path for malformed or provenance-missing proposals
  (deny, do not silently coerce or auto-correct).
- Ensure the intake path carries the caller-identity/provenance metadata
  (DAS-1608) through to whatever artifact is written, so an auditor can always
  answer "who proposed this and when."
- This handler MUST NOT itself approve, promote, or dispatch the proposal — that
  remains a separate, explicit Founder action through the existing goal-queue
  approval mechanism (no new approval path invented here).

## Acceptance criteria
- [ ] A goal proposal submitted through the A2A endpoint lands only as a board-intake artifact (never `todo`/`in_progress`, never an `approval`/gate-status write) (FR-002, SC-002).
- [ ] Provenance/identity metadata from the proposal is preserved on the landed artifact.
- [ ] A malformed/provenance-missing proposal is refused, not silently coerced.
- [ ] A negative test proves the intake handler cannot flip any gate/approval field, however it is called.
- [ ] Merged PR, green CI; `diagnostics.py` 100/100; no `project:` field (R9).

## Log
### 2026-07-24 — Senior Product Manager
Created by `/daslab-plan` (A2A Development, intake half). Depends on both Design
children (DAS-1608, DAS-1609). Gated behind DAS-1606's binding sequencing note
(after WS-B, deferred until after WS-G's proof per Q12) — left in `status:
backlog` until that gate opens.
