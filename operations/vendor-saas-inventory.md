# Vendor & SaaS Inventory — DasLab

**Owner:** Finance / Billing Analyst  
**Last updated:** 2026-05-18  
**Review cadence:** Quarterly (per CLAUDE.md success metrics)  
**Status:** Initial baseline — company is pre-external-SaaS; most tools are local/self-hosted

---

## How to Read This Document

| Column | Meaning |
|--------|---------|
| **Vendor** | Product / service name |
| **Category** | Functional grouping |
| **Plan / Tier** | Current subscription tier |
| **Monthly Cost** | USD; `$0` = free tier or self-hosted; `TBD` = not yet procured |
| **Billing Cadence** | Monthly / Annual / Usage |
| **Owner** | DasLab role accountable for renewal and usage |
| **Notes** | Contract status, DPA status, renewal date |

---

## Active — In Use Today

| # | Vendor | Category | Plan / Tier | Monthly Cost | Billing Cadence | Owner | Notes |
|---|--------|----------|-------------|--------------|-----------------|-------|-------|
| 1 | **Anthropic (Claude API)** | AI / LLM | API (usage-based) | TBD — usage-based | Per-token | COO | Runs all 32 DasLab agents (Claude Code subagents). No DPA signed yet — see compliance gap G-07. Billing tied to the Founder's Anthropic account. |
| 2 | **Memory Bank MCP** (`@allpepper/memory-bank-mcp`) | Developer Tooling | Open-source (npm) | $0 | N/A | Engineering | Self-hosted via npx; no SaaS subscription. |

---

## Committed — Approved in Architecture, Not Yet Provisioned

These tools are committed via ADR-0001 (2026-05-18) but external accounts have not been created yet. Costs are estimates; confirm before provisioning.

| # | Vendor | Category | Expected Plan | Est. Monthly Cost | Owner (when active) | Notes |
|---|--------|----------|---------------|-------------------|---------------------|-------|
| 4 | **GitHub** | Source Control + CI | Team or Enterprise | ~$4–$21/user/mo | CTO | Needed for repos + GitHub Actions CI. No account created yet per genesis spec. |
| 5 | **Vercel** | Frontend Hosting | Pro or Enterprise | ~$20–$400/mo | CTO | Planned for Next.js deployments. Deferred per genesis spec. |
| 6 | **PostgreSQL hosting** (e.g., Neon, Supabase, RDS) | Database | TBD | TBD | CTO | Primary OLTP store per ADR-0001. Provider not selected. |
| 7 | **Redis hosting** (e.g., Upstash, ElastiCache) | Cache / Ephemeral State | TBD | TBD | CTO | Cache layer per ADR-0001. Provider not selected. |

---

## Deferred / Under Evaluation

| # | Vendor | Category | Status | Notes |
|---|--------|----------|--------|-------|
| 8 | **Linear** | Project Management | Deferred | Referenced in genesis spec; not provisioned. The file-based board serves as the issue tracker for now. |
| 9 | **Slack** | Team Communication | Deferred | Not provisioned per genesis spec. |
| 10 | **Figma** | Design | Deferred | Not provisioned per genesis spec. |
| 11 | **Cyber Liability Insurance** | Insurance | Not assessed | Compliance gap S-27 (P3). Assess in Phase 3. |

---

## Monthly Burn Summary (Current)

| Category | Monthly Cost |
|----------|-------------|
| AI / LLM | TBD (usage-based) |
| Tooling & Infrastructure | $0 |
| **Total confirmed** | **$0 + Anthropic usage** |

> **Action required:** COO to pull the Anthropic API usage report and establish a monthly budget cap. This inventory will be updated once the first billing cycle closes.

---

## DPA / Compliance Status

| Vendor | DPA Signed? | Notes |
|--------|-------------|-------|
| Anthropic | No | Compliance gap G-07. COO to action — DPA available at anthropic.com. |

---

## Next Review

**Date:** 2026-08-18 (Q3 review)  
**Trigger:** Any new SaaS onboarded must be added to this file before the first invoice is paid. COO approval required for contracts per CLAUDE.md §authority.
