---
id: DAS-1608
title: A2A Design — goal-proposal intake contract, never a gate approval
status: backlog
assignee: backend-em
author: ceo
dept: engineering
priority: p1
parent: DAS-1606
goal: mustaqil-a2a-outbound
spec: 009-mustaqil-a2a-outbound
implements: [FR-002]
labels: [security]
zone: docs/design
depends_on: [DAS-1607]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 2 — Design (part A of GATE-2 for A2A OUTBOUND).**

Design the **intake contract** for what an external A2A caller may submit and how
it lands on the board:

- Define the shape of a "goal proposal" object an external caller submits (what
  fields are required, what identity/provenance metadata rides along for audit —
  who/what system proposed it, when, against what spec).
- Specify exactly where a goal proposal lands: a board-intake artifact (e.g., a
  `backlog`-status ticket or an entry ahead of the Founder-Approved Goal Queue
  gate) — never a ticket that starts in `todo`/`in_progress`, and never a write
  to any `approval`/gate-status/routing field (C3).
- Specify the refusal path: what happens when a proposal is malformed, missing
  provenance, or attempts to write a forbidden field — deny, do not silently drop
  or silently "fix."
- Explicitly state the boundary this design does NOT cross: a goal proposal is
  never, under any condition, auto-promoted to an approved/gated state — only an
  explicit Founder action (QONUN-5) can do that, and that action happens through
  the existing Founder-Approved Goal Queue mechanism, not a new one this design
  invents.

No code in this stage — HOW (transport, storage format) is decided here in
writing; building it is DAS-1611's job.

## Acceptance criteria
- [ ] A written intake-contract design document (or ADR-0040 addendum section) exists specifying the goal-proposal object shape, provenance fields, and landing artifact.
- [ ] The design explicitly states a goal proposal MUST NOT write `approval`/gate-status/routing fields and MUST NOT skip the existing Founder-Approved Goal Queue gate (QONUN-3/QONUN-5) — no new approval path invented.
- [ ] A refusal/rejection path is specified for malformed or provenance-missing proposals.
- [ ] `check_spec_consistency`/`check_links`/`board_lint` green; design ticket references SPEC-009 FR-002 and ADR-0040.

## Log
### 2026-07-24 — Senior Product Manager
Created by `/daslab-plan` (A2A Design, intake half). Depends on DAS-1607 (ADR-0040
+ SPEC review must close first). Gated behind DAS-1606's binding sequencing note
(after WS-B, deferred until after WS-G's proof per Q12) — left in `status:
backlog` until that gate opens.
