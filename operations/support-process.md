# Customer Support Process — DasLab

**Owner:** Support Lead  
**Last updated:** 2026-05-18  
**Status:** Draft — pending COO review

---

## 1. Scope

This document covers the end-to-end process for handling customer-facing support requests once DasLab ships its first product. It also provides a short-list of support tooling for COO evaluation.

> **Pre-launch note:** DasLab has no external customers yet. This process is designed now so tooling can be selected before launch and the first support interaction is handled correctly.

---

## 2. Support Channels (Planned)

| Priority | Channel | Use Case | Status |
|----------|---------|----------|--------|
| 1 | **In-app contact form / help widget** | Primary async intake | To be provisioned with product |
| 2 | **Email (support@daslab.io)** | Fallback async intake | To be set up via domain email |
| 3 | **Docs / self-service FAQ** | Deflect common questions | To be built alongside product docs |

Real-time chat (e.g., live chat widget) is deferred until the team has capacity to staff it.

---

## 3. Ticket Lifecycle

```
Intake → Triage → Assign → Work → Resolve → Close → (optional) CSAT
```

### 3.1 Intake
- All channels funnel to a single ticket queue in the chosen support tool.
- Auto-acknowledgement is sent to the customer within **15 minutes** of submission (automated).
- Spam / noise filtered by a first-pass label rule before human or agent triage.

### 3.2 Triage
- Triage SLA: **within 2 business hours** of first intake.
- Assign a priority:

  | Priority | Criteria | Initial Response Target |
  |----------|----------|------------------------|
  | **P1 — Critical** | Service down, data loss, security incident | 1 business hour |
  | **P2 — High** | Core feature broken, blocking the customer | 4 business hours |
  | **P3 — Medium** | Degraded functionality, workaround exists | 1 business day |
  | **P4 — Low** | Questions, feature requests, nice-to-haves | 3 business days |

- Tag tickets with: `product-area`, `severity`, `customer-tier` (when tiers are defined).

### 3.3 Assignment
- P1/P2: Support Lead pages the relevant product-area owner directly.
- P3/P4: Assigned to the Support Lead queue or first available agent.
- Escalation path: Support Lead → COO → CTO (for product/eng issues).

### 3.4 Work
- All customer communication happens inside the ticket thread (no side-channel replies).
- Internal notes are used for investigation context — never visible to the customer.
- If a bug is confirmed: create a linked engineering board ticket referencing the support ticket ID.

### 3.5 Resolve
- Resolution means: customer issue addressed AND customer acknowledged (or 48 h no-reply timeout passed).
- Resolution comment must include: root cause (one line), fix applied, any follow-up action items.

### 3.6 Close
- Ticket closed after resolution confirmation or 48 h no-reply.
- Optional CSAT (1-question satisfaction survey) sent on close for P1–P3 tickets.

---

## 4. Escalation Matrix

| Scenario | Escalate To | Method |
|----------|-------------|--------|
| P1 incident (service down) | COO + CTO | Immediate direct message + board ticket |
| Security / data breach | COO + Legal/Compliance Analyst | Immediate — follow incident response runbook |
| Customer requests refund or contract change | COO | Board ticket, high priority |
| Unresolved P2 > 8 business hours | COO | Board ticket + reassign |

---

## 5. Metrics (Tracked Monthly)

Per CLAUDE.md success criteria, customer support response time is tracked monthly. Target metrics:

| Metric | Target | Source |
|--------|--------|--------|
| Median first response time (P2–P3) | ≤ 4 h | Support tool report |
| P1 first response time | ≤ 1 h | Support tool report |
| Ticket resolution rate (monthly) | ≥ 90 % closed | Support tool report |
| CSAT score | ≥ 4.0 / 5.0 | Survey responses |
| Tickets escalated to engineering | Count + trend | Cross-system report |

Monthly report delivered to COO by the 5th of each following month.

---

## 6. Tool Short-List

### Selection Criteria
1. **Cost** — free or low-cost tier available at launch; scales with volume.
2. **Email integration** — must handle email-based tickets natively.
3. **Automation** — supports auto-reply, routing rules, and SLA timers.
4. **Privacy / compliance** — GDPR-ready, DPA available (relevant to G-07 gap).
5. **API** — exportable data for agent integration later.

### Candidates

| # | Tool | Free Tier | Key Strength | Key Weakness | GDPR DPA |
|---|------|-----------|-------------|--------------|----------|
| 1 | **Linear** (issues only) | Yes (free for small teams) | Already in DasLab stack decision; tight eng integration | Not a true customer support tool — no email intake | Yes |
| 2 | **Freshdesk** | Yes (up to 2 agents, email + knowledge base) | Battle-tested helpdesk; solid free tier; DPA available | UI can be cluttered; advanced automation paywalled | Yes |
| 3 | **Zammad** (self-hosted) | Free (open source) | Full control, no SaaS cost, strong email integration | Requires hosting and maintenance overhead | Self-hosted (you own data) |
| 4 | **Crisp** | Yes (2 seats, email + chat) | Clean UI, in-app chat widget, live chat ready | Limited automation on free tier | Yes |
| 5 | **HelpScout** | No free tier (~$20/user/mo) | Best-in-class UX; strong knowledge base; good API | Cost at small scale | Yes |

### Recommendation

**Freshdesk Free** for launch. Rationale:
- Zero cost until volume requires upgrade.
- Handles email intake out of the box (support@daslab.io routes directly in).
- SLA timers and auto-acknowledgement built in.
- GDPR DPA available — addresses compliance gap G-07 for the support channel.
- No engineering overhead unlike self-hosted Zammad.

If DasLab self-hosts its infrastructure on principle, **Zammad** is the alternative.

**Decision needed from COO:** approve Freshdesk Free or select an alternative from the short-list above.

---

## 7. Open Items / Next Steps

| # | Item | Owner | Due |
|---|------|-------|-----|
| 1 | COO to approve tool selection from short-list | COO | Before product launch |
| 2 | Provision support email (support@daslab.io) | COO / CTO | Before product launch |
| 3 | Configure chosen tool (routing, SLA timers, auto-ack) | Support Lead | After tool approved |
| 4 | Sign DPA with chosen support vendor | Legal / Compliance Analyst | Before first customer data ingested |
| 5 | Draft SLA document (formal, customer-facing) | Support Lead | See DAS-49 |
| 6 | Link support tickets to engineering board tickets | Support Lead + CTO | After tool provisioned |
