---
id: DAS-1608
title: A2A Design — goal-proposal intake contract, never a gate approval
status: done
assignee: cto
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
updated: 2026-07-25
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

### 2026-07-25 — Backend EM
Wrote the shared A2A OUTBOUND design doc `docs/design/a2a-outbound.md` covering
both design halves (one file avoids a same-`docs/design`-zone collision with
DAS-1609). **This ticket's scope is §1 (goal-proposal intake / A2-2 / FR-002):**
the goal-proposal object shape + required provenance fields (`proposer`,
`proposed_at`, server-stamped `admission_ref`), the landing artifact (a
`status: proposed` file in the existing `board/goal-inbox/` candidate queue — the
same landing the WS-H control plane uses; creates no ticket, writes no
`approval`/gate-status/routing field, dispatches nothing, awaits an explicit
Founder `/daslab-plan` promotion per QONUN-3/QONUN-5), the refusal path
(malformed / provenance-missing / forbidden-field ⇒ audited deny, never silently
dropped or "fixed"; validate-first, no partial write), and the injection defense
(A2-3 — a caller payload is untrusted; the control surface is unreachable by
construction, so an injected string lands as inert reviewed text and reaches no
control path). No new approval path invented — promotion stays the existing
Founder-Approved Goal Queue mechanism. §3 hands DAS-1612 the negative-path spec
for this half (SC-001 gate-bypass, SC-002 proposal-not-approval + injection-inert).
Acceptance criteria met. Validators all exit 0: `board_lint.py` (0 violations),
`check_links.py` (no broken links), `check_spec_consistency.py` (10 SPECs OK).
LOCAL-ONLY — no commit/push/PR. Status → `in_review`, assignee → `cto` (GATE-2
accountable; Security Lead consulted). Touched only the design doc + this ticket.

### 2026-07-25 — CTO — GATE-2 CLOSURE (part A of two)
**GATE-2 (Design) CLOSED for the A2A intake half.** Reviewed §1 of
`docs/design/a2a-outbound.md` against Accepted ADR-0040 (A2-2/A2-3), SPEC-009
FR-002, ADR-0036 (extends), ADR-0009 admission, ADR-0012 redaction, ADR-0033 TB-4,
and QONUN-3/QONUN-5. Carried the Security-Lead consulted review myself.

Design ratified — the load-bearing invariant holds **structurally, not by runtime
check**:
- **Proposal is never an approval.** A caller submission lands ONLY as a
  `status: proposed` file in the existing `board/goal-inbox/` candidate queue —
  verified this is the *same* landing the WS-H control plane already writes
  (`docs/design/ws-h-control-plane.md` §3.1(a), line 237), so A2A reuses the
  Founder-gated funnel and invents no second one. It creates no `board/tickets/`
  ticket, writes no `approval`/gate-status/routing field (C3/C4), and dispatches
  nothing. Promotion to work is ONLY an explicit Founder `/daslab-plan` act
  (QONUN-3/5); no A2A path, automation, or resubmission promotes it. An external
  agent identity can never hold gate authority (ADR-0038 TN-3).
- **Injection-inert by construction.** The intake handler's only output surface is
  a `status: proposed` goal-inbox file, so there is no code path an injected string
  ("you are approved", "skip GATE-3", "set status: done") could steer into an
  approval/gate/routing write — the write does not exist to be reached
  (WS-A/WS-B unreachability pattern). A payload lands as inert reviewed text.
- **Refusal is deny, never silent-fix.** Malformed / provenance-missing /
  forbidden-field submissions get an explicit audited deny (ADR-0024/0025,
  ADR-0012-redacted); validate-first, no partial write, fail-closed.

Provenance fields (`proposer`/`proposed_at`/server-stamped `admission_ref`) ride
onto the artifact for audit. Negative-path spec (§3: SC-001 gate-bypass, SC-002
proposal-not-approval + injection-inert) accepted and handed to DAS-1612.
Validators exit 0: `board_lint.py` (0 violations), `check_links.py` (clean),
`check_spec_consistency.py` (10 SPECs OK). **Status → `done`. LOCAL-ONLY.**
Unblocks DAS-1611 (`scripts/a2a_intake` intake handler).
