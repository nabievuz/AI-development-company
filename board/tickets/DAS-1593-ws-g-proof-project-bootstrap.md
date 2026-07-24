---
id: DAS-1593
title: WS-G Development — bootstrap the proof project skeleton under projects
status: done
assignee: cto
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

### 2026-07-24 — Backend EM
**Bootstrapped the proof-project skeleton (AADL §2), GATE-3 for WS-G part 3.** Resolved
`<proof-name>` from the Founder-fixed scope (Q1 = the WS-H control-plane dashboard slice,
CP-3b trigger-run) to the concrete slug **`proof-cp-trigger-run`**, and laid the canonical
lifecycle §2 skeleton under `projects/proof-cp-trigger-run/`:
- `README.md` — charter + the six-stage stage-board (GATE-1…6 status log; GATE-5 marked
  infra-gated on the tenant VM via DAS-1595).
- `SCOPE-LOCK.md` — the Founder-fixed, immutable proof scope (deliver the WS-H CP-3b
  trigger-run slice 0→100; shipped = merged + green CI + deployed to the tenant VM, Q7)
  with in/out-scope, self-widen/narrow-to-easy BLOCK semantics, and ambiguous→Clarify
  (ADR-0014). **The Founder-attributed scope hash is an explicit `[PENDING FOUNDER
  APPROVAL]` placeholder — NO Founder signature/hash was fabricated** (stamping it is a
  Founder act, per design §4.1).
- `APPROVED-GOAL-QUEUE.md` — candidate goal `cp-trigger-run`, status `candidate`, **NOT**
  `founder_approved`, carrying no `APPROVED:`/`TASDIQLANDI:` line (QONUN goal-queue law).
- `board-tickets/` — the proof's OWN board, empty by design, with a README documenting the
  Placement-Law boundary + the next step (compile after Founder approval).
- `docs/01-planning … 06-maintenance/` — the six AADL stage dirs, each with a README stub
  listing that stage's mandatory artifacts + gate checklist.

**Placement Law honored:** `projects/` is gitignored (`git check-ignore` confirms the
skeleton is untracked) — this is a local scaffold, NOT an org-repo diff. No project ticket
authored on the org `board/tickets/`; this ticket carries no `project:` field.

**The live 0→100 delivery RUN is NOT done here — it is DAS-1595-blocked** (genuinely
infra-gated: needs a provisioned tenant VM + the live autonomous run). This ticket lays
only the skeleton so the proof's GATE-1 can open in its own context once the Founder
approves the goal queue and fixes the scope-lock hash.

**Verification:** `find projects/proof-cp-trigger-run -type d` shows all 9 skeleton dirs;
`git status` clean of the skeleton (gitignored); `python3 scripts/board_lint.py` exit 0
(180 tickets, 0 violations — the DAS-1507 body-status WARN is pre-existing, unrelated);
`python3 scripts/diagnostics.py` = 100/100 (org repo unaffected); no `/home//Users`
literals in the skeleton.

Set `status: in_review`, `assignee: cto` (GATE-3 accountable, ROUTING.md). ⛔ LOCAL-ONLY:
no commit/PR/push/remote.

### 2026-07-24 — CTO (GATE-3 Development closure — part 3 of 3)
**GATE-3 CLOSED for WS-G. This ticket → `done`.** Re-reviewed the proof-project skeleton
as the GATE-3 accountable owner.

**Verified:** `find projects/proof-cp-trigger-run -type d` shows the full AADL §2 skeleton
(README stage-board, `SCOPE-LOCK.md`, `APPROVED-GOAL-QUEUE.md`, empty `board-tickets/`,
`docs/01-planning … 06-maintenance/`). Placement Law honored — `projects/` is gitignored
(`git status` clean of the skeleton; it is a local scaffold, NOT an org-repo diff), this
org-engine ticket carries no `project:` field, and no project work ticket was authored on
the org `board/tickets/` (board_lint R9 exit 0). `diagnostics.py` 100/100 (org repo
unaffected).

**Honest-placeholder posture CONFIRMED (this is the correct call):**
- `SCOPE-LOCK.md` carries an explicit `[PENDING FOUNDER APPROVAL]` placeholder for the
  scope hash — **no Founder signature/hash was fabricated** (stamping it is a Founder act,
  design §4.1). Correct: agents never forge Founder attribution.
- `APPROVED-GOAL-QUEUE.md` goal `cp-trigger-run` is `candidate`, NOT `founder_approved`,
  and carries no `APPROVED:`/`TASDIQLANDI:` line — so no project board ticket may be
  compiled yet (QONUN goal-queue law). The proof's OWN six-gate lifecycle opens later, in
  its own context, once the Founder approves the queue + stamps the scope hash.

The live 0→100 delivery RUN stays DAS-1595-blocked (genuinely infra-gated: needs a
provisioned tenant VM + the live autonomous run). This ticket only lays the skeleton, and
that is done. ⛔ LOCAL-ONLY honored: no commit/PR/push/remote this run.
</content>
