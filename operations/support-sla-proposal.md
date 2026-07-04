# Customer Support SLA Proposal — DasLab

**Owner:** Support Lead  
**Last updated:** 2026-05-18  
**Status:** Approved (COO sign-off 2026-05-18) — see Section 12  
**References:** support-process.md (internal process), DAS-47 (tool short-list)

---

## 1. Purpose

This document defines the proposed Service Level Agreement (SLA) for DasLab customer support. It covers response time commitments, resolution targets, scope of support, exclusions, and escalation guarantees. The COO must approve this before it is communicated externally.

---

## 2. Scope

This SLA applies to all paying customers of DasLab products from the date of their subscription start. Free-tier / beta users receive best-effort support with no contractual commitments (noted in Section 6).

---

## 3. Support Hours

| Tier | Support Hours | Holiday Coverage |
|------|--------------|------------------|
| Standard (all paid customers, launch) | Monday–Friday, 09:00–18:00 CET | None at launch; assess at 6 months |
| Premium (future tier, TBD) | Monday–Friday extended + on-call | To be defined when tier is created |

> **Note:** Response time SLAs are measured in **business hours** unless otherwise stated. Business hours = Monday–Friday 09:00–18:00 CET, excluding public holidays.

---

## 4. Severity Definitions

| Severity | Definition | Example |
|----------|-----------|---------|
| **S1 — Critical** | Production system down or data loss; no workaround | Product completely inaccessible; customer data missing |
| **S2 — High** | Core feature broken; workaround is difficult or unavailable | Key workflow fails; major performance degradation |
| **S3 — Medium** | Non-critical feature impaired; workaround exists | Secondary feature misbehaves; cosmetic issue blocking UX |
| **S4 — Low** | General questions, feature requests, documentation gaps | How-to questions; suggestions; typo reports |

---

## 5. Response and Resolution Targets

### 5.1 Standard Tier (All Paid Customers — Launch)

| Severity | Initial Acknowledgement | First Substantive Response | Target Resolution |
|----------|------------------------|---------------------------|------------------|
| S1 | 1 business hour | 2 business hours | 8 business hours |
| S2 | 2 business hours | 4 business hours | 2 business days |
| S3 | 1 business day | 2 business days | 5 business days |
| S4 | 3 business days | 3 business days | Best effort (no commitment) |

**Definitions:**
- *Initial acknowledgement* — automated confirmation that the ticket was received.
- *First substantive response* — a human (or agent) response that addresses the issue, asks a clarifying question, or provides an estimated resolution time.
- *Target resolution* — issue resolved or workaround provided. Complex S1/S2 issues may have an interim mitigation provided within the target, with full fix scheduled.

### 5.2 Free / Beta Users (Non-contractual)

Best-effort response; no SLA commitments. Target: respond to S1 within 2 business days.

---

## 6. Exclusions

The following are outside the scope of this SLA:

1. Issues caused by customer misconfiguration or misuse not covered by documented behavior.
2. Third-party service outages outside DasLab's control (e.g., cloud provider, DNS).
3. Beta features explicitly marked as such in product documentation.
4. Support requests submitted outside the designated channels (direct email to individual employees is not a supported channel).
5. Force majeure events.

---

## 7. SLA Credits (Proposed)

If DasLab fails to meet S1 or S2 initial response targets, customers on paid plans may request a service credit:

| Miss Scenario | Credit |
|---------------|--------|
| S1 initial response missed by > 2 h | 5% of monthly subscription fee |
| S1 initial response missed by > 8 h | 10% of monthly subscription fee |
| S2 initial response missed by > 4 h | 5% of monthly subscription fee |

Credits are applied to the next invoice on request; they do not convert to cash. Maximum credit per month: 20% of monthly fee.

> **COO note:** Credit thresholds and percentages are placeholders. Adjust to match pricing model once set.

---

## 8. Escalation Commitments

| Scenario | Commitment |
|----------|-----------|
| S1 not resolved within 8 h | COO personally engaged; customer receives hourly status updates |
| S2 not resolved within 2 business days | Support Lead escalates to CTO; customer receives daily updates |
| Customer requests executive contact | Routed to COO within 1 business day |
| Potential security incident | COO + Legal/Compliance Analyst notified immediately; incident response runbook activated |

---

## 9. Communication Standards

- All support communication occurs in the ticketing system (see DAS-47 for tool selection).
- Customers receive a ticket ID in all correspondence.
- Status updates are proactive — DasLab does not wait for the customer to follow up on unresolved S1/S2 issues.
- Root-cause summaries are provided for all resolved S1 incidents within 5 business days of resolution.

---

## 10. Review Cadence

This SLA is reviewed:

- **Quarterly** as part of the ops cadence (per CLAUDE.md success metrics).
- **On each major product launch** that changes the support surface.
- **After any S1 incident** where the SLA was not met.

---

## 11. Open Items — COO Decisions

| # | Question | COO Decision | Notes |
|---|----------|--------------|-------|
| 1 | Approve SLA credit percentages? | **Approved as proposed (placeholder)** | Re-review once pricing model is finalized; treat current % as interim. |
| 2 | Launch with Standard tier only, or also define Premium SLA now? | **Standard tier only at launch** | Define Premium when there is a customer ask or pricing tier to attach it to. |
| 3 | Support hours: CET or UTC? | **CET** | Matches team location; simpler to staff. |
| 4 | 09:00–18:00 CET or extend to cover US morning? | **09:00–18:00 CET at launch** | Revisit at 6-month review or when first US customer signs; do not over-commit before staffing exists. |
| 5 | S4 soft resolution commitment? | **No commitment at launch** | Keep S4 as best-effort; revisit only if customer feedback demands a soft target. |

---

## 12. Approval

| Role | Name | Decision | Date |
|------|------|----------|------|
| COO | COO agent | **Approved v1** | 2026-05-18 |
| Support Lead | Support Lead agent | Proposed | 2026-05-18 |

**Next steps post-approval:**
1. Support Lead finalizes tool selection in DAS-47; SLA targets feed tool requirements (ticket routing, response-time tracking, automated acknowledgement).
2. SLA credit % to be revisited once Finance publishes pricing model.
3. Schedule first quarterly SLA review for 2026-08 (per Section 10).
4. External communication of SLA blocked until Legal/Compliance review for customer-contract language (separate ticket to be opened by Support Lead).
