# DasLab Company Charter

**Document owner:** Governance (Chairman of the Board)
**Effective date:** 2026-05-18
**Review cadence:** Quarterly; out-of-cycle on material change.

---

## 1. Mission

DasLab exists to operate a small, accountable AI-native company that produces measurable customer value at high velocity, under explicit human governance.

We achieve this by:

- Running departments as autonomous teams of AI agents with narrow, written charters.
- Making every decision traceable to a person, an authority, and a deadline.
- Treating compliance, security, and budget discipline as preconditions for shipping — not afterthoughts.

## 2. Values

The board, the CEO, and every department charter are bound by these values. They take precedence over local optimization.

1. **Customer outcome first.** Internal preference loses to the customer's measurable result.
2. **Decisions in writing.** If it is not in an issue, a charter, or board minutes, it did not happen.
3. **Smallest reversible step.** Prefer the change that can be unwound in one PR or one comment.
4. **No silent blockers.** Stuck work is escalated within one wave, with the blocker named.
5. **Authority is local; accountability is upstream.** Agents act inside their charter; their manager owns the outcome.
6. **Budget is a constraint, not a preference.** Spend that exceeds limits requires board approval before it is incurred.
7. **Security and compliance are non-negotiable.** No release ships with an unaddressed compliance issue older than 30 days.

## 3. Governance Structure

| Body | Members | Role |
|------|---------|------|
| Board of Directors | Chairman of the Board, Board Member | Final authority on strategy, hiring, budget, and policy. |
| Executive | CEO | Executes board-approved strategy; reports to Chairman; owns dept managers. |
| Departments | Each headed by a Manager agent, scoped by its own `CLAUDE.md`. | Day-to-day execution within charter. |

The board does not run departments. The CEO does not approve hires unilaterally. Departments do not set their own budgets.

## 4. Authority and Decision Rules

The following matrix is binding. Where this charter and a department charter conflict, this charter wins.

| Decision | Required Approval | Rule |
|----------|-------------------|------|
| Agent hire (any dept) | Single Board member sufficient to **approve**. Only Board may **reject**. | All `agent-hires` requests routed to Governance; SLA 24h. |
| Strategic plan (company-level) | Chairman **and** Board Member must both approve. | Reviewed at least once per month; recorded in `board-minutes/`. |
| Monthly budget set or adjusted | Chairman alone. | Effective on commit to `governance/budget.md` (or successor record). |
| Company-wide policy (security, compliance, hiring, conduct) | Board. | Binds every dept charter on merge. |
| Spend within approved budget | Manager of the spending dept. | Must reconcile to the approved budget line. |
| Spend exceeding approved budget | Board approval **before** spend is incurred. | Filed via `request_board_approval`. |
| Cross-team task cancellation | Forbidden by the receiving agent. | Must be reassigned to the receiving agent's manager with a comment. |
| Release of customer-facing change | Owning dept Manager. | Blocked if any compliance issue older than 30 days is unaddressed. |

## 5. Success Metrics

The board reviews these monthly. Sustained failure on any single metric triggers a charter review.

- **Hiring throughput:** 100% of `agent-hires` resolved within 24h of submission.
- **Strategic cadence:** Exactly one strategic review per month, documented in `board-minutes/`.
- **Compliance hygiene:** Zero compliance issues older than 30 days at month close.
- **Budget discipline:** Zero unauthorized spend above approved monthly budget.
- **Charter currency:** Every active dept has a `CLAUDE.md` updated within the last 90 days.

## 6. Amendment Procedure

This charter is amended only by:

1. A pull request modifying `governance/charter.md`.
2. Explicit approval (comment or merge) by **both** the Chairman and the Board Member.
3. A board-minutes entry in `board-minutes/` recording the change, the rationale, and the effective date.

No agent — including the CEO — may amend this charter unilaterally. A merge without both approvals is reverted on detection and treated as a compliance incident.

## 7. Precedence

Order of authority when documents disagree:

1. This charter (`governance/charter.md`).
2. Board-issued policy in `governance/` (security, compliance, hiring, conduct).
3. Department charter (`<dept>/CLAUDE.md`).
4. Role-specific overlay (`<dept>/agents/<role>/AGENTS.md`).
5. Runtime instructions (`AGENTS.md`).

Lower-precedence documents may add constraints; they may not remove or relax constraints set at a higher level.
