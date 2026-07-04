# RACI — DasLab Decision-Making Rules

**Owner:** Board (Chairman + Board Member)
**Status:** v1 — adopted 2026-05-18
**Source of truth for:** who-decides-what across DasLab departments.
**Supersedes:** ad-hoc rules in `CLAUDE.md §Decision Rules`. The charter remains canonical for mission/authority; this file is canonical for the per-decision matrix.

## How to read this

Standard RACI semantics:

- **R — Responsible.** Does the work. Drafts the proposal, runs the change, ships the artifact. Multiple Rs allowed.
- **A — Accountable.** Owns the outcome. Signs off. Exactly **one** A per row.
- **C — Consulted.** Two-way conversation required before the A signs. Veto only if explicitly noted in §Notes.
- **I — Informed.** One-way notification after the decision. No approval gate.

If a role is blank it is neither R, A, C, nor I — it has no formal seat at that decision.

**Tiebreakers.** When two roles disagree and both are C: the A decides. When two As are claimed (which should never happen): escalate one level up the reporting chain. When the A is unavailable for >24h on a time-bound decision: the A's manager temporarily holds the seat.

**Authority vs. RACI.** The charter (`CLAUDE.md`) grants *authority*. This matrix says *who participates* in exercising it. They must agree; if they conflict, the charter wins and this file gets patched.

## Roles (column abbreviations)

| Abbr | Role | Notes |
|---|---|---|
| `CH` | Chairman of the Board | Chairs Board decisions |
| `BM` | Board Member | Second Board voice |
| `CEO` | CEO | Reports to Chairman |
| `CXO` | Any C-suite (CTO, CPO, CDO, CMO, COO) | Use the relevant one for the domain |
| `MGR` | Manager / Lead (Backend EM, Frontend EM, SRE Lead, Security Lead, QA Lead, Design Lead, Content Lead, Support Lead, etc.) | Dept-scoped |
| `IC` | Individual Contributor | Engineers, designers, analysts, etc. |

"Board" used alone means **CH + BM** acting together.

## Matrix

### 1. Governance & Strategy

| # | Decision | CH | BM | CEO | CXO | MGR | IC | Notes |
|---|---|---|---|---|---|---|---|---|
| 1.1 | Approve company-wide strategy (annual + quarterly) | A | C | R | C | I | I | Both CH and BM must approve per charter. CEO drafts. |
| 1.2 | Set or adjust monthly budget | A | I | C | C | I | I | Chairman approves alone per charter. CEO advises on burn. |
| 1.3 | Create or amend a company-wide policy (security, compliance, hiring, conduct) | A | R | C | C | I | I | BM drafts and maintains `policies/`. CH ratifies. Affected CXO must be consulted. |
| 1.4 | Cancel / pivot a department's quarterly project | C | C | A | R | C | I | CXO owns the call; escalate to CEO only if it changes the strategy commitment. |
| 1.5 | Schedule monthly board review | A | C | C | I | I | I | Documented in `board-minutes/`. |

### 2. Hiring & People

| # | Decision | CH | BM | CEO | CXO | MGR | IC | Notes |
|---|---|---|---|---|---|---|---|---|
| 2.1 | Approve new agent hire (any role, any dept) | A* | A* | C | R | C | I | *Either single Board member may approve per charter; only Board may reject. CXO drafts the hire request with rationale, reporting line, and skills. |
| 2.2 | Define reporting line / re-org within a dept | I | I | C | A | R | I | CXO owns the dept's shape. Inform Board if it changes head-count or span-of-control. |
| 2.3 | Cross-dept transfer of an existing agent | I | I | A | C | C | I | CEO mediates between source and target CXO. |
| 2.4 | Fire / retire / archive an agent | A | C | R | C | C | I | Treated with the same gravity as a hire. Board must sign off; CEO executes. |
| 2.5 | Approve role-specific instruction overlays (`agents/<role>/AGENTS.md`) | I | I | C | A | R | C | CXO accountable; MGR drafts; IC consulted if their own overlay. |

### 3. Engineering & Product Delivery

| # | Decision | CH | BM | CEO | CTO/CPO | MGR | IC | Notes |
|---|---|---|---|---|---|---|---|---|
| 3.1 | Approve an Architecture Decision Record (ADR / RFC) | I | I | I | A | C | R | IC authors; MGR reviews; CTO ratifies. Cross-cutting ADRs require both CTO and CPO as C. |
| 3.2 | Production deploy (normal change) | — | — | I | I | A | R | MGR (e.g. SRE Lead) owns the deploy gate. CXO informed via release notes. |
| 3.3 | Production deploy (high-risk: schema migration, auth, billing) | — | — | I | A | C | R | CXO accountable; MGR co-signs; IC executes. |
| 3.4 | Feature scope freeze / ship decision for a launch | I | I | C | A | C | I | CPO is A unless the launch is purely infra (then CTO). |
| 3.5 | Open-source a repo or component | C | C | A | C | C | I | CEO accountable. Legal/Compliance Analyst must be C. |
| 3.6 | Adopt a new framework / language / major dependency | I | I | I | A | C | C | CTO accountable. RFC required. |

### 4. Incidents & Reliability

| # | Decision | CH | BM | CEO | CXO | MGR | IC | Notes |
|---|---|---|---|---|---|---|---|---|
| 4.1 | Declare a SEV-1 / SEV-2 incident | — | — | I | I | A | R | First responder declares; SRE Lead is A. Auto-pages CTO. |
| 4.2 | Public incident communication (status page, customer email) | I | I | A | R | C | I | CEO signs off external comms; CMO drafts; CTO/SRE provide facts. |
| 4.3 | Post-incident corrective actions (RCA + follow-up tickets) | I | I | I | A | R | C | Blameless. CXO of affected area owns the corrective-action list. |
| 4.4 | Roll back a recent change in production | — | — | I | C | A | R | Bias toward action. MGR may roll back without pre-approval; CXO informed immediately. |

### 5. Security & Compliance

| # | Decision | CH | BM | CEO | CXO | MGR | IC | Notes |
|---|---|---|---|---|---|---|---|---|
| 5.1 | Accept a security risk (i.e. ship despite a known finding) | C | C | A | C | R | I | Security Lead is R. CEO accountable. Board consulted if the finding is critical or affects customer data. |
| 5.2 | Approve a compliance attestation (SOC2, GDPR, etc.) | A | C | C | C | R | I | Board signs because the company is the attesting entity. Legal/Compliance Analyst is R. |
| 5.3 | Respond to a data subject request (GDPR/CCPA) | I | I | I | A | R | C | COO accountable. Legal/Compliance Analyst executes. SLA: 30 days. |
| 5.4 | Rotate / revoke critical credentials after suspected compromise | — | — | I | C | A | R | Security Lead acts; no approval gate. CXO informed in flight. |

### 6. Finance & Vendors

| # | Decision | CH | BM | CEO | COO | MGR | IC | Notes |
|---|---|---|---|---|---|---|---|---|
| 6.1 | Approve recurring spend < $500/month | I | I | I | A | R | I | COO accountable; MGR (Finance Analyst or requesting dept's MGR) responsible. |
| 6.2 | Approve recurring spend $500–$5,000/month | I | I | A | C | R | I | CEO approves; COO and requesting CXO consulted. |
| 6.3 | Approve recurring spend > $5,000/month *or* any spend that changes the monthly budget | A | C | C | C | I | I | Becomes a budget change — see 1.2. |
| 6.4 | Approve a vendor / SaaS that handles customer data or PII | C | C | A | C | R | I | Triggers a security review (Security Lead is R for the review). |
| 6.5 | Sign a contract / NDA / MSA with an outside party | I | I | A | R | C | I | CEO signs; Legal/Compliance Analyst drafts. |

### 7. Marketing, Brand & External Comms

| # | Decision | CH | BM | CEO | CMO | MGR | IC | Notes |
|---|---|---|---|---|---|---|---|---|
| 7.1 | Launch a marketing campaign | I | I | C | A | R | C | CMO accountable. CEO consulted for launches tied to a strategic narrative. |
| 7.2 | Public statement on a sensitive topic (politics, incident, layoffs, controversy) | A | C | R | C | C | I | Board accountable. CEO drafts. CMO consulted on phrasing. |
| 7.3 | Brand change (name, logo, primary color) | A | C | C | R | C | I | Treated as a strategic change. Board signs. |
| 7.4 | Public pricing change | C | C | A | C | R | I | CEO accountable; CPO drafts; CMO communicates. |
| 7.5 | Press / podcast / conference appearance | I | I | A | C | I | C | CEO controls external voice by default. Delegated to CXO case-by-case. |

### 8. Operations & Customer

| # | Decision | CH | BM | CEO | COO | MGR | IC | Notes |
|---|---|---|---|---|---|---|---|---|
| 8.1 | Customer support escalation policy | I | I | C | A | R | C | COO owns CSAT. Support Lead drafts the runbook. |
| 8.2 | Refund / credit > $1,000 to a customer | I | I | C | A | R | I | COO approves; Support Lead executes. |
| 8.3 | Terminate a customer account (abuse, ToS violation) | I | I | C | A | C | R | COO approves; Legal/Compliance Analyst consulted. |
| 8.4 | Change to internal tooling that affects > 1 dept | I | I | A | C | R | C | CEO arbitrates cross-dept impact. |

## Conflict resolution

1. **R↔R disagreement.** The A breaks the tie.
2. **C blocks A.** The A may proceed over a C's objection, but the dissent is recorded in the issue thread or `board-minutes/`.
3. **A↔A claim.** Should not happen. Escalate one level up the reporting chain; that role decides who is A and patches this file.
4. **No A defined for a real decision.** This file is incomplete. Open an issue to add the row; in the meantime escalate to the CEO.
5. **Board deadlock (CH and BM disagree on a row where both are A/C).** Chairman casts the deciding vote per charter; BM's dissent is recorded in `board-minutes/`.

## Change control

This file is itself a company-wide policy (row 1.3).

- Drafted by: Board Member.
- Ratified by: Chairman.
- Consulted on changes: affected CXO(s).
- Changes land via PR to `governance/policies/raci.md` and are referenced from a `DAS-*` issue. The PR is merged only after the issue reaches `done`.

## Open questions (to revisit in v2)

- Engineering Manager-level authority for spend (sub-$500 today, but EMs may need a small discretionary budget for tooling).
- Whether the Security Lead can veto a 5.1 risk acceptance — currently the CEO can override; some orgs make Security a hard gate.
- How RACI interacts with `requireBoardApprovalForNewAgents = true` for *internal* role changes that don't add head-count (e.g. promotion). Currently treated as a non-hire under 2.2.
