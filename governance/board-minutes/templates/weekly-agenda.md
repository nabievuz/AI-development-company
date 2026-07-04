# Weekly Board Sync — {{YYYY-MM-DD}}

**Type:** weekly
**Chair:** Chairman of the Board
**Scribe:** Chairman (drafts within 24h)
**Required:** Chairman, Board Member, CEO
**Optional:** CXO of any dept on the agenda

**Status:** scheduled | held | cancelled
**Prior week's minutes:** [{{YYYY-MM-DD}}](../{{YYYY}}/{{YYYY-MM-DD}}-weekly.md)

---

## 0. Quorum & prior actions (3 min)

- [ ] Confirm quorum (Chairman + at least one of: Board Member, CEO).
- [ ] Walk last week's action items. Mark each: `done`, `carried`, `dropped` (with reason).

## 1. Hiring throughput — Charter §5, RACI 2.1 (5 min)

- [ ] Open `agent-hires` approvals. Any older than 24h? (Target: zero.)
- [ ] Hires landed since last sync. Reporting line confirmed?
- [ ] Hires planned this week. Who is drafting?

**Decision gate:** Approve / reject pending hires inline if quorum holds.

## 2. Compliance hygiene — Charter §5, RACI §5 (5 min)

- [ ] Open compliance issues older than 30 days. (Target: zero.)
- [ ] Pending risk acceptances (RACI 5.1) — any need board consultation?
- [ ] Credential rotations in flight (RACI 5.4) — informational.

**Decision gate:** Escalate any breach to an ad-hoc meeting before this sync ends.

## 3. Budget & spend — Charter §5, RACI 1.2, 6.x (5 min)

- [ ] CEO reports current burn vs. approved monthly budget.
- [ ] Spend approvals > $5k filed since last sync (RACI 6.3).
- [ ] Any unbudgeted spend incurred? (Target: zero — Charter Value 6.)

**Decision gate:** Chairman approves / rejects budget adjustments inline.

## 4. Strategic cadence — Charter §5, RACI 1.1, 1.5 (5 min)

- [ ] Monthly strategic review scheduled for this month? (Target: exactly one.)
- [ ] CEO's strategy-execution status: green / yellow / red, one sentence each.
- [ ] Charter currency: any dept `CLAUDE.md` older than 90 days?

## 5. Cross-team blockers & escalations (5 min)

- [ ] Cross-team task cancellations attempted (forbidden — Charter §4). Any?
- [ ] Open blockers escalated via `chainOfCommand` that the board owns.
- [ ] @-mention budget pressure or run-rate concerns from any dept.

## 6. Decisions & action items (2 min)

For each decision made in this meeting, record:

| # | Decision | Authority | A (single) | R | Follow-up issue |
|---|---|---|---|---|---|
| | | Charter §X or RACI Y.Y | role | role(s) | DAS-NNN |

Then list action items as a checklist. Each item MUST become a DAS issue before the meeting closes.

- [ ] {action} — owner: {role} — due: {date} — issue: DAS-NNN

## 7. Dissent & closing (1 min)

- Dissent recorded (per RACI §Conflict resolution): {none | summarize}
- Next sync: {{YYYY-MM-DD}} 10:00 UTC.
- Anything to push to ad-hoc this week? {none | summarize}

---

## Authoring checklist (for the Chairman after the meeting)

- [ ] Replace `{{...}}` placeholders.
- [ ] Set `Status:` to `held` or `cancelled`.
- [ ] Fill the decisions table and action items with real DAS issue links.
- [ ] Add this file to the index table in `board-minutes/README.md`.
