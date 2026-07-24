---
id: DAS-1593
title: WS-G Development — bootstrap the proof project skeleton under projects
status: todo
assignee: backend-em
author: ceo
dept: engineering
priority: p1
parent: DAS-1588
goal: mustaqil-ws-g-proof
spec: 007-mustaqil-ws-g-proof
implements: [FR-005]
labels: [governance]
zone: projects
depends_on: [DAS-1589]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 3 — Development (closes GATE-3 for WS-G, part 3).** Stand up the proof
PROJECT so it can run its OWN six-stage AADL lifecycle. This is the seam between the
org-engine WS-G machinery and the proof deliverable.

**This ticket is an ORG-ENGINE ticket** (it bootstraps a skeleton) — it MUST NOT carry
a `project:` field and MUST NOT author any project work ticket on the org board
(QONUN — Project Placement Law; board_lint R9).

- **FR-005:** create the `projects/<proof-name>/` folder from the AI-agent-lifecycle §2
  canonical skeleton — `README.md` (charter + six-stage stage-board), `APPROVED-GOAL-QUEUE.md`,
  and `docs/01-planning/ … docs/06-maintenance/`. `<proof-name>` resolves at execution
  time from the Founder-fixed scope (Q1 — the WS-H dashboard slice, e.g. `cp-trigger-run`);
  do NOT hard-code a project name into any engine file.
- The proof then runs its **OWN six AADL gates** on its **OWN board**
  (`projects/<proof-name>/board-tickets/`) — those project tickets are created LATER,
  in the project's own context, never here.
- `projects/` is gitignored (each project manages its own git repo) — this bootstrap is
  a local scaffold action, not a commit to the org repo.

Do NOT begin the proof's own Planning work here — this only lays the skeleton so the
proof's GATE-1 can open in its own context.

## Acceptance criteria
- [ ] `projects/<proof-name>/` created from the AADL §2 skeleton (README stage-board, APPROVED-GOAL-QUEUE.md, docs/01-planning..06-maintenance).
- [ ] No `project:` field on this ticket; no project work ticket authored on the org `board/tickets/` (R9).
- [ ] `<proof-name>` derived from the Founder-fixed scope (Q1) — no project name hard-coded into any engine file.
- [ ] The proof's OWN six-gate lifecycle + own board are documented as the next step (created later, in-project). `board_lint`/validators green.

## Log
### 2026-07-24 — Senior Product Manager
Created by /daslab-plan (WS-G Development, part 3). FR-005 proof-project bootstrap —
lays the `projects/<proof-name>/` AADL §2 skeleton so the proof runs its OWN six gates
on its OWN board. Org-engine ticket: no `project:` field, no project ticket on the org
board (placement law). Project name kept as a `<proof-name>` placeholder — not written
into any engine file.
</content>
