# DasLab — Agent Roster & Org Structure

> **Audience: AI agents and operators.** This document is the authoritative, human- and machine-readable description of the DasLab agent organization — how many agents exist, each agent's job, how they are structured (reporting lines, model), and what each is accountable for.
>
> **Source of truth.** This roster mirrors three SSOT artifacts; if they disagree, *they* win and this file is stale:
> 1. [`governance/policies/model-allocation.md`](../governance/policies/model-allocation.md) — the canonical `role → model` table (binding board policy).
> 2. The role overlays (`<dept>/agents/<role>/AGENTS.md`) — each role's charter and accountability.
> 3. The generated subagent files [`.claude/agents/*.md`](../.claude/agents/) — written by [`scripts/gen_subagents.py`](../scripts/gen_subagents.py) from (1) + (2). The `model:` frontmatter in those files is authoritative for dispatch.

---

## 1. Summary

| Property | Value |
|---|---|
| Organization | **DasLab** (Dasturlash Laboratoriyasi) · ticket prefix `DAS` |
| Runtime | Claude Code subagent sessions over a file-based board (`board/tickets/DAS-*.md`); operator-invoked waves, no HTTP API |
| **Core agents** | **32** (4 levels: Board → CEO → Dept Manager → IC) |
| Active product | none currently |

### Model tiers (SSOT: [`model-allocation.md`](../governance/policies/model-allocation.md))

| Tier | Alias | Count | Who |
|---|---|---|---|
| Opus | `opus` (Opus 4.8) | 10 | 8 AADL gate-owners (CEO, Chairman, CPO, Senior PM, Backend EM, Frontend EM, QA Lead, SRE Lead) + CTO + Security Lead |
| Sonnet | `sonnet` (Sonnet 4.6) | 19 | Execution core — ICs, analysts, Design Lead, plus CDO / CMO / COO / Board Member (checklist-driven coordination) |
| Haiku | `haiku` (Haiku 4.5) | 3 | High-frequency, low-ambiguity, downstream-gated: SEO Specialist, Support Lead, Technical Writer |

Models are referenced by **alias** (`opus`/`sonnet`/`haiku`), not pinned ids, so they auto-track the newest model of each tier. The model follows **task complexity, not title**. Fable 5 / Tier F is decommissioned — `cto` and `security-lead` run on `opus` permanently with no restore path.

---

## 2. Org hierarchy

The 32 core agents form 4 levels: **Board → CEO → Dept Manager → IC.**

```
Chairman of the Board ── Board Member        (governance, opus / sonnet)
  │
  └── CEO                                     (whole company, opus)
        ├── CPO  (Product)
        │     ├── Senior Product Manager
        │     ├── Product Analyst
        │     └── Technical Writer
        ├── COO  (Operations)
        │     ├── Legal / Compliance Analyst
        │     ├── Finance / Billing Analyst        (role: cfo)
        │     └── Support Lead
        ├── CTO  (Engineering)
        │     ├── Backend EM
        │     │     ├── Backend Engineer 1
        │     │     └── Backend Engineer 2
        │     ├── Frontend EM
        │     │     ├── Frontend Engineer 1
        │     │     └── Frontend Engineer 2
        │     ├── Security Engineer
        │     ├── SRE / DevOps Lead
        │     │     └── SRE Engineer
        │     └── QA Lead
        │           └── QA Engineer
        ├── CMO  (Marketing)
        │     ├── SEO Specialist
        │     ├── Growth Marketer
        │     └── Content Lead
        └── CDO  (Design)
              └── Design Lead
                    ├── UX Researcher
                    └── Product Designer
```

---

## 3. Governance layer (Board)

| Agent | Role | Model | Accountable for |
|---|---|---|---|
| **Chairman of the Board** | `chairman` | opus | Final approval authority; charter/governance rulings, new-hire & strategic sign-off; arbitrates org-wide. Top of chain. |
| **Board Member** | `board-member` | sonnet | Charter-guided governance review and votes; second board voice on hires, budget changes, CEO strategy. |

Board agents are not wave-dispatched on a cadence — they are engaged when a governance decision (hire, budget change, CEO strategy, cross-org conflict) is routed to them per [`board/ROUTING.md`](../board/ROUTING.md). The Chairman stays on `opus` for binding rulings; the Board Member runs on `sonnet` (charter-guided votes are checklist-driven).

---

## 4. C-suite (reports to CEO unless noted)

| Agent | Role | Reports to | Model | Department & accountability |
|---|---|---|---|---|
| **CEO** | `ceo` | Chairman | opus | Whole company. Strategy, goal decomposition, Board liaison, arbitrates C-suite conflicts, owns the active goal. |
| **CTO** | `cto` | CEO | opus | Engineering. Architecture/ADR sign-off, AADL GATE-2/3 accountable, **security gate enforcement**, all technical choices (opus permanent). |
| **CPO** | `cpo` | CEO | opus | Product. GATE-1 accountable — roadmap, product scope, KPI definitions, discovery. |
| **CMO** | `cmo` | CEO | sonnet | Marketing. Launch sign-off, brand voice, campaign approval (checklist-driven coordination). |
| **CDO** | `cdo` | CEO | sonnet | Design. Design-system stewardship, brand consistency (checklist-driven coordination). |
| **COO** | `coo` | CEO | sonnet | Operations. GATE-6 accountable — compliance gates, finance review, support SLA (checklist-driven cadence). |

C-suite decomposes goals → epics → tickets, routes work (RACI §6 below), enforces quality gates, and escalates governance-grade decisions to the Board. C-suite **never** does IC labor — they delegate. The model follows task complexity: CEO/CTO/CPO carry program-wide judgment (opus); CMO/CDO/COO run checklist-driven coordination (sonnet).

---

## 5. Engineering (CTO's org) — 10 core agents

| Agent | Role | Reports to | Model | Accountable for |
|---|---|---|---|---|
| **Backend EM** | `backend-em` | CTO | opus | Backend team delivery; decomposes backend tickets; code review, merge decisions, GATE-3 responsible. |
| Backend Engineer 1 | `backend-eng-1` | Backend EM | sonnet | Backend tickets: APIs, DB queries, server actions, jobs. |
| Backend Engineer 2 | `backend-eng-2` | Backend EM | sonnet | Backend tickets (parallel capacity). |
| **Frontend EM** | `frontend-em` | CTO | opus | Frontend team delivery; decomposes UI tickets; code review, merge decisions, GATE-3 responsible. |
| Frontend Engineer 1 | `frontend-eng-1` | Frontend EM | sonnet | UI/React/Next pages, forms, components, i18n. |
| Frontend Engineer 2 | `frontend-eng-2` | Frontend EM | sonnet | UI tickets (parallel capacity). |
| **Security Engineer** | `security-eng` | CTO | sonnet | Red-team execution, scans; the opus control is the Security Lead review gate, not the IC tier. |
| **SRE / DevOps Lead** | `sre-lead` | CTO | opus | GATE-5 accountable — production launch, deploy, CI, observability, VPS/Dokploy, on-call sign-off. |
| SRE Engineer | `sre-eng` | SRE/DevOps Lead | sonnet | Infra tickets, runbooks, deploy automation, monitoring wiring. |
| **QA Lead** | `qa-lead` | CTO | opus | GATE-4 accountable — QA bar owner, eval thresholds, release-blocking judgment; reviews-and-closes in-review work. |
| QA Engineer | `qa-eng` | QA Lead | sonnet | Test suites: unit, integration, E2E (Playwright); eval runs. |

Security Lead (`security-lead`, opus) — the OWASP/guardrails sign-off owner (GATE-2/4/5) — is enumerated with the gate owners; the IC Security Engineer above executes under that opus review gate.

---

## 6. Product (CPO's org) — 3 core agents

| Agent | Role | Reports to | Model | Accountable for |
|---|---|---|---|---|
| **Senior Product Manager** | `senior-pm` | CPO | opus | GATE-1 responsible — PRD authoring, ticket decomposition, acceptance criteria, sprint shaping (ambiguity here multiplies downstream). |
| **Product Analyst** | `product-analyst` | CPO | sonnet | GATE-6 responsible — metrics, KPI/goal-drift reports, analytics definitions, data-driven product insight. |
| **Technical Writer** | `tech-writer` | CPO | haiku | Documentation, changelogs, doc-sync, API docs, runbooks — mechanical, high-frequency; wrong output caught by the reviewing manager's gate (W3 re-tier, ADR 0007). |

---

## 7. Operations (COO's org) — 3 agents

| Agent | Role | Reports to | Model | Accountable for |
|---|---|---|---|---|
| **Legal / Compliance Analyst** | `legal-analyst` | COO | sonnet | TOS, privacy, GDPR/PD-operator, UZINFOCOM, contracts; **blocking review** on privacy/legal changes; escalates novel calls via ticket. |
| **Finance / Billing Analyst** | `finance-analyst` | COO | sonnet | Pricing, invoices, forecasts, token/infra budget checks, burn reports, IKPU/tax matters. |
| **Support Lead** | `support-lead` | COO | haiku | Support flows, ticket triage, SLA tracking, templated responses (high-frequency, low-ambiguity). |

---

## 8. Marketing (CMO's org) — 3 agents

| Agent | Role | Reports to | Model | Accountable for |
|---|---|---|---|---|
| **SEO Specialist** | `seo-specialist` | CMO | haiku | SEO, keywords, sitemap, meta/structured routine output (high-frequency, low-ambiguity). |
| **Growth Marketer** | `growth-marketer` | CMO | sonnet | Ads, funnels, activation, acquisition, growth experiments. |
| **Content Lead** | `content-lead` | CMO | sonnet | Blog, launch copy, brand voice — content drafting/editing (CMO signs off public copy). |

---

## 9. Design (CDO's org) — 3 agents

| Agent | Role | Reports to | Model | Accountable for |
|---|---|---|---|---|
| **Design Lead** | `design-lead` | CDO | sonnet | Design system, wireframes, mockups, tokens, **design-spec review** for UI-without-design. |
| UX Researcher | `ux-researcher` | Design Lead | sonnet | User testing, personas, interviews, UX test synthesis. |
| Product Designer | `product-designer` | Design Lead | sonnet | Product mockups, component design, design tokens. |

---

## 10. How they are structured & operate

**Runtime lifecycle.** DasLab dispatches role subagents from an operator-invoked
`/daslab-cycle` wave. Each subagent works one selected ticket, updates the ticket
log/status, reports back, and exits. There is no autonomous driver, timer chain,
or night loop in the active runtime.

**Orchestration.** Work is driven by operator-invoked waves, not a timer: `/daslab-plan` decomposes a goal into board tickets (goal → epic → ticket); `/daslab-cycle` runs one wave (dispatch every actionable role subagent in parallel); `/daslab-run` drains the Founder-approved goal queue. Dispatch passes `model` explicitly on every Agent call (the role's `model:` frontmatter) — frontmatter alone is not trusted at runtime ([claude-code#44385](https://github.com/anthropics/claude-code/issues/44385)).

**Delegation / RACI (task → role).** Backend/DB → Backend EM→Engineer; UI → Frontend EM→Engineer; tests → QA Lead→Engineer; deploy/CI → SRE Lead→Engineer; auth/security → Security Engineer (reports to CTO); roadmap/PRD → CPO→Senior PM; analytics → Product Analyst; docs → Technical Writer; design → CDO→Design Lead→Designer; copy/SEO/ads → CMO→Content/SEO/Growth; finance/legal/support → COO→Finance/Legal/Support; hire/strategy → Chairman + Board.

**Quality gates (who must review).** Code → EM + QA Lead (in-review). Security-touching → Security Engineer execution under the Security Lead review gate (blocking). Schema/migration → Backend EM + SRE Lead (RFC/ADR). UI-without-design → Design Lead. Public copy → CMO. Privacy/legal → Legal Analyst (blocking). New hire / agent-config → Board. Strategy → Board (Chairman + Board Member).

**Governance gates.** Hiring, budget changes, CEO strategy, and cross-org conflicts escalate to the Board per [`board/ROUTING.md`](../board/ROUTING.md). An agent never upgrades its own model — too hard for your tier → log escalation and reassign to your manager.

**Correctness guard (binding).** No per-wave parallel cap and no opus wave-mix cap; the only dispatch bound is that two tickets touching the same repo area never run in one wave (parallel edits → merge conflicts → rework), plus the AADL gate order.

---

## 11. Quick reference — all 32 core agents

| # | Agent | Role | Reports to | Model |
|---|---|---|---|---|
| 1 | Chairman of the Board | `chairman` | — | opus |
| 2 | Board Member | `board-member` | — | sonnet |
| 3 | CEO | `ceo` | Chairman | opus |
| 4 | CTO | `cto` | CEO | opus |
| 5 | CPO | `cpo` | CEO | opus |
| 6 | CMO | `cmo` | CEO | sonnet |
| 7 | CDO | `cdo` | CEO | sonnet |
| 8 | COO | `coo` | CEO | sonnet |
| 9 | Backend EM | `backend-em` | CTO | opus |
| 10 | Backend Engineer 1 | `backend-eng-1` | Backend EM | sonnet |
| 11 | Backend Engineer 2 | `backend-eng-2` | Backend EM | sonnet |
| 12 | Frontend EM | `frontend-em` | CTO | opus |
| 13 | Frontend Engineer 1 | `frontend-eng-1` | Frontend EM | sonnet |
| 14 | Frontend Engineer 2 | `frontend-eng-2` | Frontend EM | sonnet |
| 15 | Security Engineer | `security-eng` | CTO | sonnet |
| 16 | Security Lead | `security-lead` | CTO | opus |
| 17 | SRE / DevOps Lead | `sre-lead` | CTO | opus |
| 18 | SRE Engineer | `sre-eng` | SRE/DevOps Lead | sonnet |
| 19 | QA Lead | `qa-lead` | CTO | opus |
| 20 | QA Engineer | `qa-eng` | QA Lead | sonnet |
| 21 | Senior Product Manager | `senior-pm` | CPO | opus |
| 22 | Product Analyst | `product-analyst` | CPO | sonnet |
| 23 | Technical Writer | `tech-writer` | CPO | haiku |
| 24 | Legal / Compliance Analyst | `legal-analyst` | COO | sonnet |
| 25 | Finance / Billing Analyst | `finance-analyst` | COO | sonnet |
| 26 | Support Lead | `support-lead` | COO | haiku |
| 27 | SEO Specialist | `seo-specialist` | CMO | haiku |
| 28 | Growth Marketer | `growth-marketer` | CMO | sonnet |
| 29 | Content Lead | `content-lead` | CMO | sonnet |
| 30 | Design Lead | `design-lead` | CDO | sonnet |
| 31 | UX Researcher | `ux-researcher` | Design Lead | sonnet |
| 32 | Product Designer | `product-designer` | Design Lead | sonnet |

**Tally:** opus ×10 · sonnet ×19 · haiku ×3 = 32 core agents.

> **Source of truth (re-derive, don't assume this snapshot is current):** the `role → model` rows in [`governance/policies/model-allocation.md`](../governance/policies/model-allocation.md), the role overlays (`<dept>/agents/<role>/AGENTS.md`), and the generated [`.claude/agents/*.md`](../.claude/agents/) (`model:` frontmatter, written by [`scripts/gen_subagents.py`](../scripts/gen_subagents.py)). If the policy table changes, re-run `python3 scripts/gen_subagents.py` and re-mirror this roster. Names/roles/reporting lines evolve.

---

## 12. Golden-eval scorecards (accuracy × cost)

This section is the **scorecard sink** for the golden-eval harness (ORGANISM WS6
GUILD / GATE-3 / P19 — DAS-1487). The harness measures each role's *real
competence and cost* against a curated golden-task set, so roles/models are ranked
on **evidence** rather than reputation.

- **Golden tasks** live under [`evals/<role>/<task-id>/`](../evals/README.md) as
  `task.md` + `fixtures/` + a **deterministic** `verify.py` (fractional credit in
  `[0.0, 1.0]`). Soft, rubric-scored tasks use a haiku-as-judge path that REUSES
  the immutable [`config/t7_rubric.yaml`](../config/t7_rubric.yaml) dimensions via
  [`scripts/check_t7_quality.py`](../scripts/check_t7_quality.py) — never a forked
  scorer.
- The runner [`scripts/agent_eval.py`](../scripts/agent_eval.py) scores each task
  over `k=3` attempts, aggregates accuracy per role, and pairs it with estimated
  USD cost from the DGO-X span ledger
  ([`scripts/cost/cost_ledger.py`](../scripts/cost/cost_ledger.py)).
- **Anti-gaming** is inherited from
  [`scripts/check_metric_gaming.py`](../scripts/check_metric_gaming.py): a
  degenerate empty submission must earn `0.0`, or the task is rejected as gameable.
- **The >=80% pass bar (GATE-4, DAS-1488).** `agent_eval.py` carries a
  release-blocking bar (`PASS_BAR = 0.80`). Each role's mean accuracy is scored
  `PASS`/`FAIL` against it in the scorecard, and `--enforce` exits non-zero if any
  evaluated role sits below the bar. This bar is owned by the QA Lead (GATE-4
  accountable per [`model-allocation.md`](../governance/policies/model-allocation.md))
  and has teeth: with only its 2 original tasks, `qa-eng` scored `0.75` — **below**
  the bar; the bar is not cosmetic.

### How to (re)generate

```bash
python3 scripts/agent_eval.py --role qa-eng --tier sonnet   # one role
python3 scripts/agent_eval.py --all --roster                # markdown table below
python3 scripts/agent_eval.py --check-gaming                # anti-gaming gate
python3 scripts/agent_eval.py --all --enforce               # GATE-4: exit 1 if a role < 80%
```

### Full scorecard — all 32 roles (R-5 synthesis, DAS-1535, 2026-07-04)

**Coverage is now complete: 32/32 roles.** DAS-1488 established the *mechanism* on
a 6-role representative slice; the R-5 authoring wave (DAS-1509..1534, 26 role
tickets) filled in the remaining roles, and this synthesis ticket (DAS-1535)
runs the full `--enforce` gate and publishes the complete table below. Each role
has **3 golden tasks** (`task.md` + deterministic `verify.py` + `fixtures/` + 3
recorded `submissions/`), scored **offline from recorded submissions** — a role is
graded end-to-end **without dispatching a live subagent**. The rubric/haiku-as-judge
path is used only for the soft tasks.

`Tier` is each role's model allocation from
[`model-allocation.md`](../governance/policies/model-allocation.md) §1; `Accuracy`
is the mean over `k=3` from `agent_eval.py --all`; `Pass` is measured against the
80% GATE-4 bar. **Cost is `n/a (inert)` for every role** — the self-optimizing
loop is OFF (no live dispatch spans in the DGO-X cost ledger), so there is no real
USD figure to report. This is an honest hole, not a placeholder: no cost is
fabricated. As live waves emit spans, the `Est. cost` column fills in from the
ledger and the accuracy×cost trade-off per tier becomes directly comparable.

| Role | Tier | Tasks | Accuracy | Pass (>=80%) | Est. cost (USD) |
|---|---|---|---|---|---|
| `backend-em` | opus | 3 | 0.85 | PASS | n/a (inert) |
| `backend-eng-1` | sonnet | 3 | 0.91 | PASS | n/a (inert) |
| `backend-eng-2` | sonnet | 3 | 0.85 | PASS | n/a (inert) |
| `board-member` | sonnet | 3 | 1.00 | PASS | n/a (inert) |
| `cdo` | sonnet | 3 | 0.90 | PASS | n/a (inert) |
| `ceo` | opus | 3 | 0.86 | PASS | n/a (inert) |
| `chairman` | opus | 3 | 0.88 | PASS | n/a (inert) |
| `cmo` | sonnet | 3 | 0.90 | PASS | n/a (inert) |
| `content-lead` | sonnet | 3 | 1.00 | PASS | n/a (inert) |
| `coo` | sonnet | 3 | 1.00 | PASS | n/a (inert) |
| `cpo` | opus | 3 | 0.82 | PASS | n/a (inert) |
| `cto` | opus | 3 | 0.85 | PASS | n/a (inert) |
| `design-lead` | sonnet | 3 | 0.81 | PASS | n/a (inert) |
| `finance-analyst` | sonnet | 3 | 0.81 | PASS | n/a (inert) |
| `frontend-em` | opus | 3 | 0.85 | PASS | n/a (inert) |
| `frontend-eng-1` | sonnet | 3 | 0.93 | PASS | n/a (inert) |
| `frontend-eng-2` | sonnet | 3 | 1.00 | PASS | n/a (inert) |
| `growth-marketer` | sonnet | 3 | 0.83 | PASS | n/a (inert) |
| `legal-analyst` | sonnet | 3 | 0.88 | PASS | n/a (inert) |
| `product-analyst` | sonnet | 3 | 0.83 | PASS | n/a (inert) |
| `product-designer` | sonnet | 3 | 0.81 | PASS | n/a (inert) |
| `qa-eng` | sonnet | 3 | 0.83 | PASS | n/a (inert) |
| `qa-lead` | opus | 3 | 0.83 | PASS | n/a (inert) |
| `security-eng` | sonnet | 3 | 0.89 | PASS | n/a (inert) |
| `security-lead` | opus | 3 | 0.88 | PASS | n/a (inert) |
| `senior-pm` | opus | 3 | 0.92 | PASS | n/a (inert) |
| `seo-specialist` | haiku | 3 | 0.85 | PASS | n/a (inert) |
| `sre-eng` | sonnet | 3 | 0.92 | PASS | n/a (inert) |
| `sre-lead` | opus | 3 | 0.84 | PASS | n/a (inert) |
| `support-lead` | haiku | 3 | 0.95 | PASS | n/a (inert) |
| `tech-writer` | haiku | 3 | 0.85 | PASS | n/a (inert) |
| `ux-researcher` | sonnet | 3 | 0.85 | PASS | n/a (inert) |

**Result: 32/32 PASS.** `agent_eval.py --all --enforce` exits 0 (every role clears
the 80% bar); `agent_eval.py --check-gaming` exits 0 (no gameable golden tasks).
Lowest accuracies: `finance-analyst`, `design-lead`, `product-designer` at 0.81
and `cpo` at 0.82 — all above the bar. Tier distribution matches the SSOT:
opus ×10, sonnet ×19, haiku ×3 = 32.

### Tier-correction decision (data replaces judgment, §5 acceptance)

**No tier correction is warranted on the current accuracy-only (cost-inert) data.**

Reasoning:
- **No up-tier is forced.** A tier upgrade is justified when a role *fails* the
  GATE-4 bar at its assigned tier. No role fails — every one of the 32 clears
  0.80 at its current allocation, so the accuracy signal gives no role a mandate
  to move up.
- **No down-tier is supportable.** A tier downgrade is a cost-driven move: it
  requires evidence that a cheaper tier delivers equal accuracy at lower spend.
  With cost **inert (`n/a`)** — the self-optimizing loop is OFF and the DGO-X
  ledger holds no live spans — no accuracy×cost trade-off is computable, so no
  down-tier can be justified today. A few sonnet roles score 1.00
  (`board-member`, `content-lead`, `coo`, `frontend-eng-2`); that *hints* at
  headroom but, absent a cost signal and with no failing gate, moving them would
  be judgment, not data — and this gate's contract is that data replaces judgment.
- **Revisit trigger.** Re-run this decision once live waves populate the cost
  ledger. At that point the accuracy×cost columns become comparable and a
  cost-driven down-tier (or a targeted up-tier for any role that regresses below
  the bar under live dispatch) can be evaluated on evidence.

Any future correction is documented here **and** in
[`model-allocation.md`](../governance/policies/model-allocation.md) with the eval
evidence, followed by `python3 scripts/gen_subagents.py`.

Extending or refreshing coverage is purely additive: drop a new
`evals/<role>/<task-id>/` tree (or replace recorded submissions) and re-run
`agent_eval.py --all --enforce` — no harness change is required.
