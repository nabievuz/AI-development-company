# Monthly Burn Report — DasLab

**Report period:** YYYY-MM (e.g., 2026-05)  
**Prepared by:** Finance / Billing Analyst  
**Reviewed by:** COO  
**Date prepared:** YYYY-MM-DD

---

## 1. Executive Summary

| Metric | This Month | Prior Month | Δ |
|--------|-----------|-------------|---|
| Total confirmed spend | $— | $— | — |
| AI / LLM (Anthropic) | $— | $— | — |
| Infrastructure & tooling | $— | $— | — |
| New vendors onboarded | — | — | — |
| Budget alerts | — | — | — |

> **Status:** Green / Yellow / Red — one-line narrative on month-over-month trend.

---

## 2. AI / LLM Costs (Anthropic Claude API)

> Source: Anthropic usage dashboard. Pull at month close from the Founder's Anthropic billing account.

| Model | Input tokens | Output tokens | Cache read tokens | Total cost (USD) |
|-------|-------------|---------------|------------------|-----------------|
| claude-opus-4-x | — | — | — | $— |
| claude-sonnet-4-6 | — | — | — | $— |
| claude-haiku-4-5 | — | — | — | $— |
| **Total** | | | | **$—** |

**Top cost drivers this month:**
- Agent / use-case driving highest spend: —
- Cache hit rate: —% (target ≥ 60%)

**Budget cap status:** [ ] Within cap ($—) | [ ] Approaching cap | [ ] Over cap

---

## 3. Active SaaS Subscriptions

> Source: `vendor-saas-inventory.md`. Update if any changes occurred this period.

| # | Vendor | Category | Plan | Monthly Cost | Change vs. Prior Month | Notes |
|---|--------|----------|------|-------------|----------------------|-------|
| 1 | Anthropic (Claude API) | AI / LLM | Usage-based | $— | — | See §2 above |
| 2 | Memory Bank MCP | Developer Tooling | Open-source | $0 | none | |
| **Total** | | | | **$—** | | |

---

## 4. Committed-Not-Yet-Active Vendors

Track estimated future burn from approved-but-not-yet-provisioned tools.

| Vendor | Category | Est. Monthly Cost | Target Provision Date | Owner | Status |
|--------|----------|------------------|----------------------|-------|--------|
| GitHub | Source Control / CI | ~$4–21/user/mo | TBD | CTO | Not provisioned |
| Vercel | Frontend Hosting | ~$20–400/mo | TBD | CTO | Not provisioned |
| PostgreSQL hosting | Database | TBD | TBD | CTO | Provider not selected |
| Redis hosting | Cache | TBD | TBD | CTO | Provider not selected |
| **Estimated pipeline** | | **TBD** | | | |

---

## 5. Compliance & Billing Hygiene

| Item | Status | Owner | Due |
|------|--------|-------|-----|
| Anthropic DPA signed | [ ] Yes / [x] No — gap G-07 | COO | Overdue |
| Anthropic monthly budget cap set | [ ] Yes / [ ] No | COO | This quarter |
| All invoices downloaded and filed | [ ] Yes / [ ] No | Finance | End of month |
| New vendors added to inventory | [ ] Yes / [ ] N/A | Finance | Real-time |
| Quarterly inventory review due? | [ ] Yes (next: 2026-08-18) / [ ] No | Finance | Q3 |

---

## 6. Action Items

> Carry forward open items; close completed ones.

| # | Item | Owner | Due | Status |
|---|------|-------|-----|--------|
| 1 | Sign Anthropic DPA | COO | — | Open |
| 2 | Set Anthropic monthly budget cap | COO | — | Open |
| 3 | Select PostgreSQL hosting provider | CTO | — | Open |
| 4 | Select Redis hosting provider | CTO | — | Open |

---

## 7. Notes & One-Off Items

> Anything that does not fit the tables above: disputed charges, refunds, contract renegotiations, trial periods, etc.

- (none this period)

---

## How to Use This Template

1. Copy this file to `reports/burn/YYYY-MM.md` at month close.
2. Fill in §1 summary numbers last, after all other sections are complete.
3. Pull Anthropic usage from the billing dashboard and complete §2.
4. Confirm §3 against the current `vendor-saas-inventory.md`; update inventory if anything changed.
5. Update §4 if any committed vendor moved to active.
6. Carry forward open items in §6; add new ones as they arise.
7. Mark the report reviewed by COO before filing.
