# Monthly Strategic Review — {{YYYY-MM-DD}}

**Type:** monthly
**Chair:** Chairman of the Board
**Scribe:** Chairman (drafts within 24h)
**Required:** Chairman, Board Member, CEO, all CXOs (CTO, CMO, CPO, CDO, COO, CFO via Finance Lead)
**Optional:** Dept Managers when their team's metric is red

**Status:** scheduled | held | cancelled
**Replaces:** that week's weekly sync (Charter §5, cadence)
**Prior month's minutes:** [{{YYYY-MM-DD}}](../{{YYYY}}/{{YYYY-MM-DD}}-monthly.md)

---

## 0. Quorum & prior actions (5 min)

- [ ] Confirm quorum: Chairman + Board Member + CEO present (mandatory).
- [ ] Walk prior monthly action items. Mark each: `done`, `carried`, `dropped` (with reason).
- [ ] Carry-over from weekly syncs this month: any unresolved decision punted to monthly?

## 1. Success metrics roll-up — Charter §5 (10 min)

Each metric: green / yellow / red + one sentence. Red triggers a charter review per Charter §5.

| # | Metric | Target | Actual (this month) | Status | Owner |
|---|---|---|---|---|---|
| 5.1 | Hiring throughput | 100% of `agent-hires` resolved < 24h | | | Chairman |
| 5.2 | Strategic cadence | Exactly one strategic review documented | | | Chairman |
| 5.3 | Compliance hygiene | Zero issues > 30 days at month close | | | Legal/Compliance Analyst → COO |
| 5.4 | Budget discipline | Zero unauthorized spend > approved monthly | | | Finance Lead → CEO |
| 5.5 | Charter currency | Every active dept `CLAUDE.md` < 90 days | | | CEO |

**Decision gate:** Any red metric → schedule a remediation ad-hoc within 7 days, owner named.

## 2. Strategy review & approval — Charter §4 (15 min)

Per Charter §4, the strategic plan requires Chairman **and** Board Member approval, reviewed at least monthly.

- [ ] CEO walks current strategic plan: what shipped this month, what's next month's bet, what's at risk.
- [ ] Each CXO: one-sentence "what would change my dept's trajectory" — board pushback welcome.
- [ ] Explicit approval recorded: **Chairman approves: yes / no / conditional.** **Board Member approves: yes / no / conditional.**

**Decision gate:** Both approvals required to keep the plan in force. A single `no` freezes new cross-dept commitments until reconciled.

## 3. Budget — Charter §4, RACI 1.2, 6.x (10 min)

- [ ] Finance Lead reports: opening balance, spend by dept, closing balance, run-rate vs. monthly cap.
- [ ] Variances > 10% per dept: explained inline.
- [ ] Unauthorized spend events this month (Charter Value 6). Target: zero.
- [ ] Chairman sets / adjusts next month's budget (single-signer authority, Charter §4).

**Decision gate:** Chairman records next month's monthly budget here; commits to `governance/budget.md` (or successor) within 24h.

## 4. Dept reviews — round-robin (15 min)

Each CXO, 2 minutes:

- One thing that worked. One thing that didn't. One thing they need from the board.

Dept order (rotates monthly to avoid recency bias): COO → CTO → CMO → CPO → CDO → CEO.

**Decision gate:** Board commits / declines each "thing they need" inline. Declines must give a reason.

## 5. Policy & compliance — Charter §4, §7 (5 min)

- [ ] Policies merged or amended since last monthly. Any need explicit board ratification?
- [ ] Compliance issues opened, closed, still open > 30 days (Value 7).
- [ ] Pending charter amendments (Charter §6): require Chairman + Board Member approval to merge.
- [ ] Risk register: any new accepted risks the board should know about?

## 6. Hiring & org changes (5 min)

- [ ] Hires landed this month (count + role).
- [ ] Hires planned next month (count + role + sponsor dept).
- [ ] Org chart deltas: new reporting lines, role retirements, agent terminations.
- [ ] Any hire SLA breach (> 24h, Charter §5.1) this month — root cause + fix.

## 7. Cross-team & external commitments (5 min)

- [ ] Cross-team task cancellations attempted this month (forbidden, Charter §4). Any?
- [ ] External commitments (customer, vendor, regulator) with board exposure.
- [ ] @-mention budget run-rate per dept — flag any dept approaching pause threshold.

## 8. Decisions & action items (5 min)

For each decision made in this meeting, record:

| # | Decision | Authority | A (single) | R | Follow-up issue |
|---|---|---|---|---|---|
| | | Charter §X or RACI Y.Y | role | role(s) | DAS-NNN |

Then list action items as a checklist. Each item MUST become a DAS issue before the meeting closes.

- [ ] {action} — owner: {role} — due: {date} — issue: DAS-NNN

## 9. Dissent & closing (5 min)

- Dissent recorded (per RACI §Conflict resolution): {none | summarize}
- Next monthly: first Monday of {{next-month}}, 10:00 UTC.
- Next weekly: {{YYYY-MM-DD}} 10:00 UTC.
- Any ad-hoc triggered by this meeting? {none | list}

---

## Authoring checklist (for the Chairman after the meeting)

- [ ] Replace `{{...}}` placeholders.
- [ ] Set `Status:` to `held` or `cancelled`.
- [ ] Fill the success metrics table with real numbers (not blanks).
- [ ] Record explicit Chairman + Board Member strategy approval in §2.
- [ ] Fill the decisions table and action items with real DAS issue links.
- [ ] Add this file to the index table in `board-minutes/README.md`.
