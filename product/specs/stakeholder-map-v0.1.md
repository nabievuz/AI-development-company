# DasFlow Stakeholder Map

**Date:** 2026-05-18
**Owner:** CPO (DAS-35)
**Project:** Roadmap Cycle 1
**Status:** Draft — for cross-dept validation before Q3 themes lock

---

## Purpose

For each MVP product area in [DasFlow MVP Brief v0.1](./mvp-brief-v0.1.md), name the **internal owner**, **internal contributors / consumers**, and **external stakeholders** (users, channels, regulators). Used to: route specs to the right reviewers, decide approval chains, and avoid blind spots when scoping work.

Roles below refer to DasLab internal agents unless prefixed *External:*.

---

## Cross-cutting roles (apply to every area)

| Role | Function |
|------|----------|
| CPO | Owns the area's existence on the roadmap, approves scope changes. |
| Senior PM | Owns the spec end-to-end for any single area assigned. |
| CTO | Feasibility sign-off, architectural review. |
| Design Lead / Product Designer | UX direction for any user-facing surface. |
| QA Lead | Acceptance criteria and release gate. |
| Security Lead | Threat-model review for anything that touches auth, budget, or external integrations. |
| Legal / Compliance Analyst | ToS, data-handling, and billing-model review. |
| CEO | Final go/no-go on launch. |

---

## Area 1 — Agent Roster

Define roles, models, system prompts, reporting hierarchy via UI.

| Stake | Who | Why |
|-------|-----|-----|
| Owner | Senior PM | Core org-model surface; primary differentiator. |
| Engineering | Backend EM, Backend Engineer 1, Frontend EM, Frontend Engineer 1 | CRUD APIs + roster UI. |
| Design | Design Lead, Product Designer | Hierarchy visualization; role-creation flow. |
| Research | UX Researcher | Validate "org model" framing resonates ([assumption #2 in MVP brief](./mvp-brief-v0.1.md)). |
| Analytics | Product Analyst | Instrument roster-creation funnel, time-to-first-agent. |
| Support | Support Lead | Onboarding scripts, FAQ. |
| External — primary | Indie Studio Founder | Defines & manages the roster directly. |
| External — secondary | Early-stage SaaS team lead | Sets up roster for the team. |
| External — channel | CodeCanyon audience | Templates / starter packs surfaced here. |

---

## Area 2 — Task Inbox

Create issues, assign to agents, see live status.

| Stake | Who | Why |
|-------|-----|-----|
| Owner | Senior PM | Day-one utility surface; drives WAU. |
| Engineering | Backend Engineer 2, Frontend Engineer 2 | Issue model, list/detail views, real-time status. |
| Design | Product Designer | Inbox IA, empty states, assignment UX. |
| Research | UX Researcher | Tests whether non-technical co-founders can create tasks. |
| Analytics | Product Analyst | Tasks-per-workspace, completion rate (success metric). |
| QA | QA Engineer | Cross-browser, state-transition coverage. |
| External — primary | Indie Studio Founder | Creates tasks, monitors output. |
| External — secondary | SaaS team PM / EM | Assigns tasks across multiple agents. |

---

## Area 3 — Heartbeat Runner

Agents execute on-demand or on a schedule.

| Stake | Who | Why |
|-------|-----|-----|
| Owner | CTO (engineering-led area; PM is consulted, not primary) | Core execution engine; reliability dominates UX. |
| Engineering | Backend EM, Backend Engineer 1, SRE / DevOps Lead, SRE Engineer | Runner, scheduler, queue, retry semantics. |
| Security | Security Lead, Security Engineer | Sandboxing, secret handling, prompt-injection surface. |
| Analytics | Product Analyst | Run-success rate, duration distribution. |
| QA | QA Lead | Failure-mode test plan, chaos cases. |
| Finance | Finance / Billing Analyst | Cost per run; feeds into budget cap. |
| External — primary | Indie Studio Founder | Indirect — only sees outcomes, not the runner. |
| External — operational | DasLab SRE on-call (internal user) | Owns the pager for runner failures. |

---

## Area 4 — Threaded Comments

Agents and users in one thread per task.

| Stake | Who | Why |
|-------|-----|-----|
| Owner | Senior PM | Observability + async collaboration surface. |
| Engineering | Backend Engineer 2, Frontend Engineer 1 | Comment model, mentions, real-time updates. |
| Design | Product Designer | Thread density, agent-vs-user differentiation. |
| Content | Technical Writer | Default agent comment style guide. |
| Research | UX Researcher | Whether users trust agent comments. |
| Analytics | Product Analyst | Comment volume per task; mention-driven re-wake rate. |
| External — primary | Indie Studio Founder | Reads agent updates, replies inline. |
| External — secondary | SaaS team members (multi-user) | Multi-human + multi-agent threads. |

---

## Area 5 — Hard Budget Cap

Monthly spend limit with auto-pause.

| Stake | Who | Why |
|-------|-----|-----|
| Owner | CPO + Finance / Billing Analyst (co-owned) | Trust gate; pricing-model dependency. |
| Engineering | Backend EM, Backend Engineer 1 | Server-side enforcement, pause/resume semantics. |
| Frontend | Frontend Engineer 2 | Usage dashboard, cap-reached UI. |
| Security | Security Lead | Bypass risk; tenant isolation of budget state. |
| Legal | Legal / Compliance Analyst | Billing T&Cs, disclosure of auto-pause behavior. |
| Marketing | CMO, Content Lead, Growth Marketer | Communicates value of "no surprise bills" externally. |
| Support | Support Lead | Handles cap-hit support tickets. |
| Analytics | Product Analyst | Cap-hit frequency by tier; informs tier limits. |
| External — primary | Indie Studio Founder | Direct consumer — biggest stated worry per persona research. |
| External — economic buyer | SaaS team's finance owner | Approves the line item; needs predictability. |
| External — regulator-adjacent | Payment processor (e.g. Stripe) | Refund / dispute behavior tied to auto-pause. |

---

## Cross-area approval chains (proposed)

| Decision type | Chain |
|---------------|-------|
| Scope change to any MVP area | Senior PM → CPO → CTO (if feasibility impact) |
| New external integration | Senior PM → Security Lead → Legal → CPO |
| Pricing or tier limit change | CPO → Finance → CMO → CEO |
| Launch readiness | QA Lead → Security Lead → CPO → CEO |

---

## Open questions (for next review)

1. **Board involvement** — MVP brief explicitly excludes board/governance approval flow. Confirm with CEO whether Board Member / Chairman of the Board are consulted (info-only) or excluded entirely for v1.
2. **CDO scope** — CDO not currently mapped to any area; confirm whether brand system for DasFlow rolls under CDO or CMO.
3. **COO involvement** — Operational readiness (support staffing, incident playbooks) likely belongs to COO; needs explicit hand-off on launch chain.
4. **External advisors / design partners** — Not yet identified. CPO to nominate 3–5 indie-dev design partners by end of discovery.

---

## Next steps

| Action | Owner | By |
|--------|-------|-----|
| Circulate to CTO, CMO, COO, CEO for sign-off on chains | CPO | 2026-05-21 |
| Resolve open questions 1–4 above | CPO | 2026-05-22 |
| Lock v1.0 of stakeholder map before Q3 themes proposal | CPO | 2026-05-25 |

---

*Roles and external personas derived from [MVP brief v0.1](./mvp-brief-v0.1.md) and current company agent roster. Update whenever an MVP area is added, removed, or re-scoped.*
