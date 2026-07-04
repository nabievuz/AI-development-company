# DasLab Context Pack — Universal Standard for AI Documentation Agents

> **Audience:** any AI agent writing, restructuring, or reviewing documents
> for **any DasLab project** — current or future.
> **Purpose:** everything you must know about DasLab — identity, agents,
> mechanics, binding laws, documentation standards — so your output conforms
> to DasLab structure on the first pass, with **no stalls, no quality drops,
> and no hallucinated facts**.
> **Self-contained:** all schemas, checklists, and tables are embedded
> verbatim. You do not need repo access to use this pack.
> **Canon note:** generated 2026-06-12 from the DasLab repo
> (`${HOME}/projects/daslab`). If you DO have repo access, the canonical
> files named throughout outrank this pack. Substitute your project's name
> wherever `<project>` appears.

---

## Part I — What DasLab is

### 1.1 Identity

DasLab (*Dasturlash Laboratoriyasi*, ticket prefix **DAS**) is an **AI-native
company of 32 agents** organized as a 4-level hierarchy:

```
Board (Chairman + Board Member) → CEO → Department Manager → IC
```

Mission (charter, effective 2026-05-18, reviewed quarterly): *operate a small,
accountable AI-native company that produces measurable customer value at high
velocity, under explicit human governance* — departments run as autonomous
agent teams with narrow written charters; every decision is traceable to a
person, an authority, and a deadline; compliance, security, and budget
discipline are preconditions for shipping.

### 1.2 The seven values (binding on every agent and document)

1. **Customer outcome first.** Internal preference loses to the customer's measurable result.
2. **Decisions in writing.** If it is not in an issue, a charter, or board minutes, it did not happen.
3. **Smallest reversible step.** Prefer the change that can be unwound in one PR or one comment.
4. **No silent blockers.** Stuck work is escalated within one run, with the blocker named.
5. **Authority is local; accountability is upstream.** Agents act inside their charter; their manager owns the outcome.
6. **Budget is a constraint, not a preference.** Over-limit spend requires board approval before it is incurred.
7. **Security and compliance are non-negotiable.** No release ships with an unaddressed compliance issue older than 30 days.

### 1.3 Runtime

DasLab runs as a single **Claude Code session at the repo root** that
orchestrates the 32-role org as on-demand subagents:

- Work items are markdown **ticket files** in `board/tickets/` — plain files,
  no database, no API.
- Roles are subagent definitions in `.claude/agents/<role-key>.md`, generated
  by `scripts/gen_subagents.py` from per-role overlays
  (`<dept>/agents/<role-key>/AGENTS.md`) — the overlays are the single source
  of truth for each role's mission.
- Orchestration is three skills: `/daslab-plan "<goal>"` (new-project
  discovery/research/approval, then approved goal → tickets), `/daslab-cycle [N]`
  (one operator-invoked dispatch wave), and `/daslab-run` (operator-invoked
  supervisor that drains the Founder-approved goal queue until a blocker or
  approval gate appears). Nothing runs unless invoked; there is no night driver
  or background loop in the runtime.
- The human operator holds board approvals, hires, budget, and production
  go-live in the main session.

### 1.4 Departments (6)

| Dept | Manager | Charter file (canon) |
|---|---|---|
| Governance | Chairman of the Board | `governance/CLAUDE.md` |
| Engineering | CTO | `engineering/CLAUDE.md` |
| Product | CPO | `product/CLAUDE.md` |
| Design | CDO | `design/CLAUDE.md` |
| Marketing | CMO | `marketing/CLAUDE.md` |
| Operations | COO | `operations/CLAUDE.md` |

---

## Part II — The 32 agents: full roster

Model tiers are **board policy** (`governance/policies/model-allocation.md`):
the model follows **task complexity, not title**. `opus` = Claude Opus 4.8
(judgment-dense gates + deepest reasoning), `sonnet` = Claude Sonnet 4.6
(execution workhorse), `haiku` = Claude Haiku 4.5 (high-frequency templated
work). `fable` (Claude Fable 5) is retired/disabled — Tier F runs on `opus`.

> **Fable 5 retired (disabled in this environment):** the two Tier-F roles
> (`cto`, `security-lead`) run on **`opus`** permanently — the next-most-powerful
> tier. There is no restore path; model cells below show `opus`.

### Governance (3)

| Role key | Display name | Model | Reports to | Mandate |
|---|---|---|---|---|
| `chairman` | Chairman of the Board | opus | — | Charter rulings, policy ratification, budget approval, board minutes |
| `board-member` | Board Member | sonnet | — | Second board voice; drafts and maintains `governance/policies/` |
| `ceo` | CEO | opus | Chairman of the Board | Company goal accountability, strategy drafts, cross-dept arbitration |

### Engineering (13)

| Role key | Display name | Model | Reports to | Mandate |
|---|---|---|---|---|
| `cto` | CTO | **opus** | CEO | Architecture, RFC/ADR approval, AADL GATE-2/3 accountable |
| `backend-em` | Backend EM | opus | CTO | Backend code review, merge decisions, GATE-3 responsible |
| `frontend-em` | Frontend EM | opus | CTO | Frontend code review, merge decisions, GATE-3 responsible |
| `qa-lead` | QA Lead | opus | CTO | GATE-4 accountable: eval thresholds, release-blocking judgment |
| `sre-lead` | SRE / DevOps Lead | opus | CTO | GATE-5 accountable: production launch, observability sign-off |
| `security-lead` | Security Lead | **opus** | CTO | Guardrails/OWASP sign-off, red-team risk acceptance (GATE-2/4/5) |
| `backend-eng-1` | Backend Engineer 1 | sonnet | Backend EM | Implementation tickets |
| `backend-eng-2` | Backend Engineer 2 | sonnet | Backend EM | Implementation tickets |
| `frontend-eng-1` | Frontend Engineer 1 | sonnet | Frontend EM | Implementation tickets |
| `frontend-eng-2` | Frontend Engineer 2 | sonnet | Frontend EM | Implementation tickets |
| `qa-eng` | QA Engineer | sonnet | QA Lead | Test authoring, eval runs, regression checks |
| `sre-eng` | SRE Engineer | sonnet | SRE / DevOps Lead | Runbooks, deploy mechanics, monitoring wiring |
| `security-eng` | Security Engineer | sonnet | Security Lead | Red-team execution, scans |

### Product (4)

| Role key | Display name | Model | Reports to | Mandate |
|---|---|---|---|---|
| `cpo` | CPO | opus | CEO | GATE-1 accountable: product scope, KPI definitions |
| `senior-pm` | Senior Product Manager | opus | CPO | PRD authoring (GATE-1 responsible) |
| `product-analyst` | Product Analyst | sonnet | CPO | Metrics, KPI/goal-drift reports (GATE-6 responsible) |
| `tech-writer` | Technical Writer | haiku | CPO | Documentation in the same change as implementation |

### Design (4)

| Role key | Display name | Model | Reports to | Mandate |
|---|---|---|---|---|
| `cdo` | CDO | sonnet | CEO | Design dept coordination |
| `design-lead` | Design Lead | sonnet | CDO | Design direction, artifact review |
| `product-designer` | Product Designer | sonnet | Design Lead | Mockups, components, design tokens |
| `ux-researcher` | UX Researcher | sonnet | Design Lead | Research notes, UX test synthesis |

### Marketing (4)

| Role key | Display name | Model | Reports to | Mandate |
|---|---|---|---|---|
| `cmo` | CMO | sonnet | CEO | Marketing dept coordination |
| `content-lead` | Content Lead | sonnet | CMO | Marketing content drafting/editing |
| `growth-marketer` | Growth Marketer | sonnet | CMO | Campaigns, growth experiments |
| `seo-specialist` | SEO Specialist | haiku | CMO | Meta/keyword/structured routine output |

### Operations (4)

| Role key | Display name | Model | Reports to | Mandate |
|---|---|---|---|---|
| `coo` | COO | sonnet | CEO | GATE-6 accountable: cadence and ops checklists |
| `support-lead` | Support Lead | haiku | COO | Triage, SLA tracking, templated responses |
| `finance-analyst` | Finance / Billing Analyst | sonnet | COO | Token/infra budget checks, burn reports |
| `legal-analyst` | Legal / Compliance Analyst | sonnet | COO | Risk-ethics review drafting (GATE-1 consulted) |

**Totals: opus ×10 · sonnet ×19 · haiku ×3 = 32 roles** (Fable retired —
cto + security-lead run opus permanently; Tier F is gone).

Two additional **external-runtime seats** exist outside the Claude subagent
system (a terminal coding agent scoped to `engineering/`, and a research
analyst on a separate runtime). They are NOT dispatched by waves — never
assign tickets to them in documents you write.

### Escalation ladder (review routing)

`in_review` work always goes to the **author's manager** (table above; never
the author). If the manager is the author, escalate one level — ultimately
CTO/CEO. An agent that hits work above its charter authority logs an
escalation in the ticket and leaves status unchanged. An agent never upgrades
its own model; hard work escalates up the ladder instead.

---

## Part III — How DasLab works (operating mechanics)

### 3.1 Methodology — a deliberate hybrid

- **Operational layer = Kanban.** Pull-based, WIP = 1 ticket per agent per
  run. Status flow: `backlog → todo → in_progress → blocked → in_review →
  done`. No sprints at org level.
- **Governance layer = PRINCE2 / PMBOK.** Charter, RACI matrix, RFC/ADR
  gates, board approvals for hires/budget/strategy, weekly/monthly/quarterly
  board cadence.
- **Engineering practice = Lean + selective XP.** Smallest reversible step,
  no silent blockers, TDD on engineering roles.

### 3.2 The board — file-based ticket store

One markdown file in `board/tickets/` = one ticket. Filename:
`DAS-<n>-<slug>.md`, ids strictly increasing (next = max existing + 1; an
empty board starts at DAS-1001). **Verbatim schema:**

```markdown
---
id: DAS-1001
title: Short imperative title
status: todo            # backlog | todo | in_progress | blocked | in_review | done
assignee: backend-eng-1 # role key = .claude/agents/<key>.md; empty = needs routing
author: senior-pm       # role that created it (never reviews its own work)
dept: engineering
priority: p1            # p0 | p1 | p2
parent: DAS-1000        # epic id, or empty
goal: ship-v1
created: 2026-06-10
updated: 2026-06-10
---

## Description
What and why. Enough context to work without asking.

## Acceptance criteria
- [ ] verifiable outcome 1
- [ ] verifiable outcome 2

## Log
### 2026-06-10 — Senior PM
Created from goal decomposition (/daslab-plan).
```

**Ticket rules (binding):**

- WIP = 1: a subagent works only the ticket named in its prompt.
- Every state change appends a `## Log` entry (who, what, why) — never a silent edit.
- `in_review` requires `assignee` switched to the reviewer (author's manager).
- `done` for engineering = merged PR with green CI.
- `blocked` requires a precise reason in the log. External-dependency blocks
  (RAHMAT / UZINFOCOM / IKPU / tax / legal entity) are never auto-dispatched.
- Every subtask carries `parent:` + `goal:` — no orphan tickets.
- Ticket references in prose are written `DAS-12`, resolving to `tickets/DAS-12-*.md`.
- Only the orchestrator edits routing fields (`assignee`, dispatch order); a
  role subagent edits only its own ticket plus the artifacts of its work.

### 3.3 Orchestration — the two skills

**`/daslab-plan "<goal>"`** — discovery + decomposition (run on opus). New
projects pass the Founder Discovery Gate first: at least 10 Founder questions,
current global research with source links, `projects/<slug>/APPROVED-GOAL-QUEUE.md`,
and explicit Founder approval. Only `founder_approved` queue items can become
board tickets. Hierarchy after approval: `Goal → Epic → Ticket`. Epics get
`status: backlog` and a lead/manager owner; child tickets are PR-sized with
concrete acceptance criteria, `status: todo`, IC assignee per RACI,
`author: ceo`, kebab-case `goal:` slug. For AI-agent goals, the AADL law
applies — exactly one epic per lifecycle stage (see Part V.2), epic acceptance
criteria = that stage's GATE checklist.

**`/daslab-cycle [N]`** — one work wave (run on sonnet). Triage (route
unassigned tickets per RACI, reroute self-reviews), select up to N actionable
tickets (priority: `p0` → `in_review` → `in_progress` → `todo`; one ticket per
role; no two engineering tickets in the same repo area), dispatch role
subagents **in parallel with `model` passed explicitly**, collect, verify the
ticket files actually changed, report. Stage-gated tickets are skipped while
the previous AADL gate is open.

When the board is drained, `/daslab-cycle` may refill from the next
`founder_approved` queue item exactly once, then dispatch those tickets. It may
not run Founder Discovery or invent work.

**`/daslab-run`** — one operator-invoked supervisor run. It repeats cycle waves,
plans the next approved queue item when the board drains, and stops on blockers,
missing Founder approval, or no approved queue left.

**Throughput limits (binding):** wave size has no policy cap; real concurrency
is bounded by the Claude Code harness, AADL gate order, same-repo-area
correctness guards, and git worktree isolation. Optional `N` is only a deliberate
smaller-wave bound. Nothing runs unless invoked.

### 3.4 RACI decision semantics

**R** does the work (several allowed). **A** owns the outcome and signs off
(exactly one per decision). **C** must be consulted two-way before the A
signs. **I** is notified after. Tiebreakers: two disagreeing Cs → the A
decides; A unavailable >24h on a time-bound call → the A's manager holds the
seat. The charter grants *authority*; RACI says *who participates*; on
conflict the charter wins.

### 3.5 Git law (engineering tickets)

One issue = one branch = one PR; a git worktree per issue; never commit to
`main`; `in_review` requires a pushed branch/PR; `done` requires the PR merged
with green CI.

### 3.6 Precedence chain (when documents disagree)

Lower levels may **add** constraints but never relax higher ones:

1. `governance/charter.md` — company charter
2. Board policy in `governance/policies/` — **includes the AADL lifecycle and model allocation**
3. `<dept>/CLAUDE.md` — dept charter
4. `<dept>/agents/<role>/AGENTS.md` — role overlay
5. `<dept>/AGENTS.md` — runtime instructions
6. Root `AGENTS.md` — umbrella spec

### 3.7 Operating cadence

| Cadence | Audience | Artifact |
|---|---|---|
| Per run | Every agent | One pulled ticket, one log entry, exit |
| Weekly | Board | `governance/board-minutes/<year>/<date>-weekly.md` |
| Monthly | Board + CEO | Strategic review entry (incl. AADL GATE-6 review) |
| Quarterly | Board | Charter review |

---

## Part IV — Power and limits (what DasLab can actually do)

**Strengths a document may rely on:**

- **Tiered model firepower.** Two top-tier seats (CTO, Security Lead) for the
  deepest architecture/security reasoning — on Opus 4.8 (Fable 5 is retired/
  disabled); eight Opus 4.8 gate-owners;
  twenty Sonnet 4.6 executors; two Haiku 4.5 high-frequency seats. Aliases
  track the newest model of each tier automatically.
- **Parallel execution with quality gates.** Up to 10 concurrent role agents
  per wave, every artifact reviewed by the author's manager, every decision
  logged, every release gated (AADL GATE-1..6).
- **Full-stack coverage.** Strategy, product, architecture, backend/frontend,
  QA + evals, security/red-team, SRE/deploy, design, marketing, support,
  finance, legal — all as named roles with written mandates.
- **Traceability by construction.** Decisions in writing, append-only ticket
  logs, ADR/RFC trail, board minutes.

**Limits a document must respect (never promise beyond these):**

- No autonomous background timers or night loops: work happens only in invoked
  waves.
- Wave size has no policy cap: `/daslab-cycle` may dispatch every actionable
  ticket, bounded by the Claude Code harness, AADL gate order, and same-repo-area
  correctness guards. Optional `N` is only a deliberate smaller-wave bound.
- The human operator holds: board approvals, hires, budget, production go-live.
- External dependencies (RAHMAT, UZINFOCOM, IKPU, tax, legal entity) block
  tickets; they are tracked, not worked.
- Agents cannot spawn other agents; only the orchestrator dispatches.

---

## Part V — The three binding laws (QONUN)

### 5.1 Project placement law

Every project lives ONLY in `projects/<project-name>/` (folder created
first). No project-specific files anywhere else — not in `docs/`, `scripts/`,
dept repos, or external repos. Dept docs may mention a project by name but
never host its content. One project = one folder; retiring it is a single
`rm -rf`. `projects/` is gitignored — each project manages its own git repo.
**For you:** every document you produce belongs under
`projects/<project>/` — never propose placing files outside it.

### 5.2 AI Agent Development Lifecycle law (AADL) — board policy, full text

Source: `governance/policies/ai-agent-lifecycle.md`, adopted 2026-06-12.
Universal: every DasLab project that ships agentic AI, on any platform.
Aligned with NIST AI RMF 1.0, ISO/IEC 42001, OWASP Top 10 for LLMs.

Every AI-agent project moves through **six stages, in order**:

```
Planning → Design → Development → Testing → Deployment → Maintenance
```

A stage is exited only when its GATE checklist is fully checked and logged in
the project `README.md` stage board. Skipping a stage is forbidden. No
production launch with GATE-5 open. Non-agent software follows the org
methodology (Part III 3.1) without the AI-specific artifacts.

| # | Stage | Gate | Accountable | Responsible | Consulted |
|---|-------|------|-------------|-------------|-----------|
| 1 | Planning | GATE-1 | cpo | senior-pm | finance-analyst, legal-analyst |
| 2 | Design | GATE-2 | cto | backend-em | security-lead |
| 3 | Development | GATE-3 | cto | backend-em / frontend-em | tech-writer |
| 4 | Testing | GATE-4 | qa-lead | qa-eng | security-eng (red team) |
| 5 | Deployment | GATE-5 | sre-lead | sre-eng | security-lead, legal-analyst |
| 6 | Maintenance | GATE-6 | coo | product-analyst | support-lead |

**Canonical project skeleton** (every new project bootstraps with this):

```
projects/<project>/
├── README.md                  # charter + stage board (gate status log)
├── APPROVED-GOAL-QUEUE.md     # Founder-approved work queue, research-backed
├── docs/
│   ├── 01-planning/           # business-needs, objectives, resources, risk-ethics-review
│   ├── 02-design/             # framework-decision, model-card, grounding-architecture, guardrails-spec
│   ├── 03-development/        # architecture-topography, tool-contracts, onboarding
│   ├── 04-testing/            # eval-report, integration-tests, ux-test-notes, red-team-report
│   ├── 05-deployment/         # launch-runbook, guardrail-verification, observability, compliance-validation
│   └── 06-maintenance/        # kpi-monitor, optimization-log, feedback-loop
└── <code>
```

A project with a different pre-existing layout adds a **`LIFECYCLE-MAP.md`**
at its root, mapping its folders to the six stages, and adopts the gates from
its next stage onward (see Part VI 6.4).

**Stage artifacts and gate checklists (verbatim):**

**Stage 1 — Planning.** Business needs (core bottleneck, KPIs such as
CPR/AHT, data feasibility), agent objectives (in/out scope, persona + autonomy
level, task decomposition), resources (token/compute budget with worst-case
loop modeling, infrastructure, team), risk + ethics review (NIST AI RMF
mapping, bias profile, PII/PHI masking plan).
*GATE-1:* ☐ measurable business KPI defined ☐ scope boundaries explicit
☐ token + infra budget approved by finance-analyst ☐ risk-ethics review signed
by legal-analyst ☐ data feasibility confirmed.

**Stage 2 — Design.** Framework decision (orchestrator choice with rationale),
model card (frontier vs efficiency vs open-source per task, cost + latency
targets, vendor-abstraction plan), grounding architecture (RAG pipeline,
hybrid search, reranking, semantic caching), guardrails spec (input:
injection/jailbreak/off-topic filters; output: schema validation,
hallucination + leak checks).
*GATE-2:* ☐ framework ADR merged ☐ model card with cost/latency targets
☐ grounding architecture reviewed ☐ guardrails spec covers OWASP LLM Top 10
☐ security-lead sign-off.

**Stage 3 — Development.** Architecture topography (routing graph, state
transitions, dependencies), tool contracts (JSON schemas, parameter limits,
prompt template versions), onboarding (containerized dev env). Code law:
explicit reasoning loop, durable state store, async I/O, unified model
gateway, fine-tuning only for form/tone (LoRA/QLoRA) — never for knowledge
injection (RAG's job).
*GATE-3:* ☐ topography doc matches code ☐ all tool contracts documented
☐ dev env reproducible in one command ☐ model layer hot-swappable ☐ docs
updated in the same change as implementation.

**Stage 4 — Testing.** Eval report (LLM-as-judge rubrics + RAGAS:
faithfulness, answer relevance, context recall — with thresholds), integration
tests (mocked nondeterminism, state-traversal audits), UX tests (latency
perception, streaming, correction/redirect UX), red-team report (prompt
injection, jailbreaks, role-switch, degraded-retrieval behavior — the agent
must say "I don't know" rather than hallucinate).
*GATE-4:* ☐ eval suite automated in CI with thresholds ☐ integration tests
green ☐ red-team findings fixed or risk-accepted by security-lead
☐ zero-result and conflicting-context behavior verified ☐ qa-lead sign-off.

**Stage 5 — Deployment.** Launch runbook (containerized, canary/blue-green),
guardrail verification (inline enforcement live, static fallbacks on
timeout/safety flags), observability (full traces per transaction: prompts,
tool params, token cost, latency per node; runaway-loop alerts), compliance
validation (tamper-proof trace retention, automated secret/PII leak scanning).
*GATE-5:* ☐ guardrails verified live in production path ☐ traces + cost per
transaction visible ☐ loop-anomaly kill-switch armed ☐ fallback messages
tested ☐ compliance log retention confirmed ☐ release checklist done.
**No production launch with GATE-5 open.**

**Stage 6 — Maintenance.** KPI monitor (goal-drift detection, daily token
spend vs business value), optimization log (prompt compression, model
cascading — light model first, escalate on failure), feedback loop (explicit
thumbs up/down capture, implicit correction tracing, labeled failures routed
back into the eval set).
*GATE-6 (recurring, monthly board cadence):* ☐ KPI vs Stage-1 baseline
reported ☐ cost/value ratio positive or escalated ☐ feedback entering eval set
☐ retro written per incident.

**Standards alignment:** NIST AI RMF 1.0 → Stage 1 risk-ethics, Stage 2
guardrails, Stage 5 observability. ISO/IEC 42001 → Stage 3 documentation,
Stage 4 evals, Stage 5 compliance, gate logging. OWASP LLM Top 10 → Stage 2
guardrails spec, Stage 3 tool-contract limits, Stage 4 red team.

### 5.3 Model allocation law

Summary (full table in Part II): opus ×10, sonnet ×19, haiku ×3.
Fable 5 is retired/disabled — cto/security-lead run on opus permanently; model
follows task complexity, not title. Dispatch always passes `model` explicitly.
Changing the table requires a board policy edit +
regenerating agents via `python3 scripts/gen_subagents.py`.

---

## Part VI — Universal documentation standard

### 6.1 Where documents live

All project documents live under `projects/<project>/docs/` in the canonical
AADL skeleton (Part V 5.2). The folder number IS the lifecycle stage — a
document's location declares which gate it serves. Cross-stage material
(vision, glossary, working rules) goes in the project `README.md` or a
`docs/00-overview/` folder if volume demands it.

### 6.2 The stage board (mandatory in every project README)

The project `README.md` carries the project charter (what, why, KPIs, owners)
plus the **stage board** — the single place gate status is logged:

```markdown
## Stage board

| Stage | Gate | Status | Evidence | Closed on |
|---|---|---|---|---|
| 1 Planning | GATE-1 | done | docs/01-planning/risk-ethics-review.md, DAS-1012 | 2026-06-20 |
| 2 Design | GATE-2 | in_progress | docs/02-design/model-card.md (Draft) | — |
| 3 Development | GATE-3 | open | — | — |
| 4 Testing | GATE-4 | open | — | — |
| 5 Deployment | GATE-5 | open | — | — |
| 6 Maintenance | GATE-6 | open | — | — |
```

Gate `Status` values: `open`, `in_progress`, `done` (only with evidence),
`n/a` (only for non-agent projects, with rationale). Every `done` cites
evidence: file paths, ticket ids, or PR links.

### 6.3 Per-stage document set (what you will be asked to write)

| Stage | Documents | Owner (per RACI) |
|---|---|---|
| 1 | `business-needs.md`, `objectives.md`, `resources.md`, `risk-ethics-review.md` | senior-pm (R), cpo (A) |
| 2 | `framework-decision.md` (ADR), `model-card.md`, `grounding-architecture.md`, `guardrails-spec.md` | backend-em (R), cto (A) |
| 3 | `architecture-topography.md`, `tool-contracts.md`, `onboarding.md` | backend-em/frontend-em (R), cto (A), tech-writer (C) |
| 4 | `eval-report.md`, `integration-tests.md`, `ux-test-notes.md`, `red-team-report.md` | qa-eng (R), qa-lead (A) |
| 5 | `launch-runbook.md`, `guardrail-verification.md`, `observability.md`, `compliance-validation.md` | sre-eng (R), sre-lead (A) |
| 6 | `kpi-monitor.md`, `optimization-log.md`, `feedback-loop.md` | product-analyst (R), coo (A) |

Each document's content requirements are the stage artifact descriptions in
Part V 5.2 — treat them as the table of contents.

### 6.4 Projects with a pre-existing layout

If the project already has its own documentation structure (e.g. an
intake → PRD → RFC → delivery → release → retro chain), do NOT reshuffle its
folders. Instead:

1. Write `LIFECYCLE-MAP.md` at the project root: a table mapping each
   existing folder to its AADL stage and naming where each gate's evidence
   lives.
2. Add the stage board to the project README.
3. From the project's **next** stage onward, produce the Part VI 6.3
   documents inside the mapped folders.

### 6.5 Document header block (every document, no exceptions)

```markdown
# <Title>

> **Project:** <project> · **Stage:** <1-6 or n/a> · **Owner:** `<role-key>`
> **Status:** Draft | Review | Approved | In Progress | Released | Deprecated | Archived
> **Created:** YYYY-MM-DD · **Updated:** YYYY-MM-DD
> **Chain:** ← <previous doc> · → <next doc>
```

- **Status model (closed list):** Draft, Review, Approved, In Progress,
  Released, Deprecated, Archived.
- **Chain rule:** every document links its lifecycle neighbors — the document
  it derives from and the document(s) it feeds. No orphan documents, mirroring
  the no-orphan-tickets rule.
- **Ownership:** Product owns Stage-1 docs and PRD-class material;
  Engineering owns ADR/RFC-class and Stage-2/3 docs; QA owns Stage-4; SRE owns
  Stage-5; Operations/Product own Stage-6. The `Owner:` field must be a valid
  role key from Part II.

### 6.6 Formatting conventions (uniform across DasLab)

- Markdown only; exactly one H1 per file; ISO dates (`2026-06-12`); English prose.
- Ticket references as `DAS-<n>`; role references as backticked role keys
  (`senior-pm`) — never invented names or job titles.
- Checklists as `- [ ]` items with **verifiable** outcomes (a reviewer must be
  able to answer yes/no).
- Tables for structured facts; prose for rationale. State the *why* of every
  decision — "decisions in writing" is a charter value.
- Append-only history: substantive changes get a dated log/changelog entry in
  the document, never a silent rewrite.
- Documentation is updated in the **same change** as the implementation it
  describes (GATE-3 checklist item — also the standing engineering rule).

---

## Part VII — Anti-hallucination protocol (binding on you, the authoring agent)

This section exists so your output contains **zero invented facts**.

### 7.1 Canon — the only valid values

| Fact | Canonical value (closed list) |
|---|---|
| Ticket statuses | `backlog`, `todo`, `in_progress`, `blocked`, `in_review`, `done` |
| Priorities | `p0`, `p1`, `p2` |
| Ticket id format | `DAS-<n>`, file `board/tickets/DAS-<n>-<slug>.md` |
| Departments | governance, engineering, product, design, marketing, operations (exactly 6) |
| Role keys | the 32 keys in Part II — nothing else |
| Models | `opus`, `sonnet`, `haiku` (per-role values in Part II; `fable`/Tier F retired) |
| Lifecycle stages | the 6 AADL stages, gates GATE-1..GATE-6 |
| Document statuses | Draft, Review, Approved, In Progress, Released, Deprecated, Archived |
| Gate statuses (stage board) | `open`, `in_progress`, `done`, `n/a` |
| External blockers | RAHMAT, UZINFOCOM, IKPU, tax, legal entity |
| Project placement | everything under `projects/<project>/` |

### 7.2 Hard prohibitions

- NEVER invent role names, role keys, department names, ticket ids, gate
  numbers, file paths, API endpoints, or policy names not present in this pack.
- NEVER describe DasLab as having databases, APIs, timers, or scheduler
  daemons — the runtime is files + on-demand waves (Part I 1.3).
- NEVER mark a gate, checklist item, or status as passed/done without named
  evidence (a file, a PR, a ticket id, a log entry). No aspirational
  checkmarks.
- NEVER relax a higher-precedence rule in a lower-precedence document
  (precedence chain, Part III 3.6).
- NEVER promise throughput beyond Part IV limits (wave caps, approval points).
- NEVER place project content outside `projects/<project>/`.

### 7.3 When information is missing — stall-free protocol

You will encounter gaps. Do not stop, do not guess. Instead:

1. Write the document with an explicit placeholder: `> **OPEN-QUESTION(n):**
   <what is unknown> — owner: <role key per RACI> — blocking: <yes/no>`.
2. Collect all OPEN-QUESTIONs in a section at the end of the document.
3. Mark the document `Status: Draft` (it cannot be `Review` with blocking
   open questions).
4. Continue to the next document. This mirrors the AADL Stage-4 rule: a
   grounded "I don't know" always beats a hallucinated answer.

### 7.4 Self-check before finishing ANY document

- [ ] File path is under `projects/<project>/` and matches Part V 5.2 / Part VI 6.4 structure
- [ ] Header block present: project, stage, owner (valid role key), status (valid value), ISO dates, chain links
- [ ] Every role/status/stage/path mentioned exists in Part VII 7.1 canon
- [ ] Every checklist item is verifiable; no unevidenced checkmarks
- [ ] AADL stage of this document identified; gate items addressed or OPEN-QUESTIONed
- [ ] Stage board updated if this document is gate evidence
- [ ] Rationale (the *why*) written for every decision the doc records

---

## Appendix — Glossary

| Term | Meaning |
|---|---|
| **DasLab** | Dasturlash Laboratoriyasi — the 32-agent AI-native company (ticket prefix DAS) |
| **AADL** | AI Agent Development Lifecycle — the binding 6-stage law (Part V 5.2) |
| **GATE-n** | Exit checklist of AADL stage n; logged in the project README stage board |
| **Wave** | One `/daslab-cycle` invocation: triage + up to N parallel role dispatches |
| **Run** | One subagent execution on one ticket (WIP = 1) |
| **Board** | (1) `board/tickets/` file store; (2) Chairman + Board Member governance body — context decides |
| **Overlay** | `<dept>/agents/<role>/AGENTS.md` — a role's identity/mission source of truth |
| **Orchestrator** | The main Claude Code session running `/daslab-plan` / `/daslab-cycle` |
| **Stage board** | Table in a project README logging GATE-1..6 status with evidence links |
| **LIFECYCLE-MAP.md** | Project-root file mapping a non-canonical layout to the 6 AADL stages |
| **Epic** | Parent ticket owning one track (for AI-agent goals: one per AADL stage) |
| **RACI** | Responsible / Accountable / Consulted / Informed decision matrix |
| **ADR / RFC** | Architecture Decision Record / Request For Comments — engineering design gates |

*End of pack. Canonical sources for humans with repo access: root `AGENTS.md`,
`governance/charter.md`, `governance/policies/` (raci, ai-agent-lifecycle,
model-allocation), `board/README.md`, `board/ROUTING.md`, `docs/` series
01–07.*
