# DasLab MVP Brief

**Date:** 2026-05-18
**Author:** Senior PM
**Status:** Discovery draft — requires CPO validation and user confirmation
**Project:** Roadmap Cycle 1

---

## Problem

Individual developers and small indie studios who want AI agents doing real work — code review, ticket triage, doc generation, QA — face a high setup tax: raw API calls, prompt engineering, no coordination layer, no observability. Hosted options are either locked into a single use-case (Copilot = coding only) or enterprise-only with six-figure contracts (Devin, Imbue). There is no lightweight, opinionated SaaS that lets a solo dev or a 2–5-person team spin up a coordinated AI workforce in under an hour.

---

## Target User

**Primary persona — Indie Studio Founder**
Solo dev or small founding team (2–5) building a software product. Technical. Charges hourly or ships on a marketplace (CodeCanyon, Gumroad, AppSumo). Already calling Claude/GPT APIs directly; wants agents doing grunt work so they can focus on product direction. Currently duct-taping scripts, cron jobs, and Discord bots to approximate agent behavior.

**Secondary persona — Early-stage SaaS team**
10–30-person startup that has bought Copilot but wants agents to own entire workflows (PR review, changelog, support triage) rather than just suggest lines of code.

---

## Product Hypothesis

**DasFlow — AI Agent Workforce for Developer Teams**

A hosted, opinionated multi-agent platform. You define roles (Engineer, PM, QA) and goals; DasFlow deploys coordinated agents that execute tasks, report status, and hand off to each other — without writing orchestration code.

**Core differentiator:** structured org model (roles + reporting lines + budgets) instead of flat prompt-runners. Built on the same patterns DasLab uses internally.

---

## MVP Feature Set (target: 6-week build)

| # | Feature | Rationale |
|---|---------|-----------|
| 1 | **Agent roster** — define roles, models, system prompts, reporting hierarchy via UI | Core value: org-shaped AI, not just API wrappers |
| 2 | **Task inbox** — create issues, assign to agents, see live status | Tangible output loop; proves agent utility day one |
| 3 | **Agent runner** — agents execute on-demand or on a schedule | Core execution engine |
| 4 | **Threaded comments** — agents and users in one thread per task | Observability + async collaboration |
| 5 | **Hard budget cap** — monthly spend limit with auto-pause | Safety gate; required for enterprise trust |

### Explicitly excluded from MVP

- Board/governance approval workflow
- Design, Marketing, and Operations agent types
- GitHub / Slack / Jira integrations
- Multi-workspace (single workspace per account at MVP)
- Mobile app

---

## Business Model

**Freemium SaaS.**

| Tier | Price | Limits |
|------|-------|--------|
| Free | $0/mo | 3 agents, 30 tasks/mo |
| Starter | $29/mo | 10 agents, 300 tasks/mo |
| Growth | $99/mo | 50 agents, unlimited tasks |
| Enterprise | Custom | SSO, audit logs, SLA |

DasLab absorbs LLM cost and marks up. No per-token billing exposed to users. Budget cap enforced server-side.

---

## Success Metrics (MVP + 60 days post-launch)

| Metric | Target |
|--------|--------|
| Signups (30 days) | 50 |
| Week-4 WAU retention | ≥ 20 % |
| Tasks completed / active workspace / week | ≥ 3 |
| NPS at day 60 | ≥ 30 |
| Paid conversion (free → paid, 30 days) | ≥ 8 % |

---

## Top Risks

| Risk | Mitigation |
|------|-----------|
| A local-first agent-orchestration tool already does this | DasFlow is cloud-hosted, zero-ops, SaaS — orthogonal positioning |
| LLM cost margin compression | Budget cap + usage dashboards; price anchored to value, not tokens |
| Slow time-to-value → churn | Day-0 onboarding creates a working agent in < 5 minutes; template library |
| Founders' market (too niche) | Secondary persona (early SaaS) expands TAM; CodeCanyon channel for indie dev reach |

---

## Assumptions to Validate (next 2 weeks)

1. Indie devs will pay $29/mo for managed agent coordination (vs. DIY with raw APIs).
2. "Org model" framing (roles + hierarchy) resonates more than "workflow automation."
3. Hosted > local for the primary persona (low ops tolerance).
4. CodeCanyon audience is a viable early-adopter channel given InboxAI V5 traction.

---

## Next Steps

| Action | Owner | By |
|--------|-------|-----|
| CPO validates or redirects hypothesis | CPO | 2026-05-20 |
| 5 user interviews (indie dev persona) | Senior PM | 2026-05-25 |
| Competitive analysis: Devin, Devon, Bolt, Replit Agent | Senior PM | 2026-05-23 |
| CTO feasibility check (hosting model, cost structure) | CTO | 2026-05-22 |
| Final detailed spec → `specs/mvp-dasflow-v1.md` | Senior PM | 2026-06-01 |

---

*This brief is a discovery hypothesis, not a committed roadmap. All assumptions above must be validated with real users before entering detailed spec and engineering scoping.*
