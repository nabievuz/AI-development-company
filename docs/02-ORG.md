# 02 — Organization

> The 32-agent org: chart, roster, reporting lines, and models.
> **Source of truth** is [`governance/policies/model-allocation.md`](../governance/policies/model-allocation.md)
> (the canonical per-role model table) + the per-role overlays
> (`<dept>/agents/<role>/AGENTS.md`) + the generated `.claude/agents/<role>.md`
> subagent shims. There is no API and nothing to "re-fetch" — this doc mirrors
> those files.

## Where it lives

- **Model per role** — the canonical `| role | model |` table in
  [`governance/policies/model-allocation.md`](../governance/policies/model-allocation.md).
  `scripts/gen_subagents.py` parses it and writes `model:` into every
  `.claude/agents/<role>.md`. To check the live roster, read the overlays or
  grep `^model:` in `.claude/agents/*.md`.
- **Reporting lines / charters** — `<dept>/CLAUDE.md` and the role overlays.
- **Regenerate after any change** — re-run `python3 scripts/gen_subagents.py`;
  it rewrites all 32 agent files + `board/ROUTING.md`. Never hand-edit those.

## Org chart

```
Chairman of the Board ───┐ (Board — governance, approvals; wake-on-demand)
Board Member ────────────┘
        │
       CEO  ★ accountable for the whole company goal
        ├── CTO  (Engineering)
        │     ├── Backend EM ── Backend Engineer 1, Backend Engineer 2
        │     ├── Frontend EM ── Frontend Engineer 1, Frontend Engineer 2
        │     ├── QA Lead ── QA Engineer
        │     ├── SRE / DevOps Lead ── SRE Engineer
        │     └── Security Lead ── Security Engineer
        ├── CPO  (Product)
        │     ├── Senior Product Manager
        │     ├── Product Analyst
        │     └── Technical Writer
        ├── CDO  (Design)
        │     └── Design Lead ── Product Designer, UX Researcher
        ├── CMO  (Marketing)
        │     ├── Content Lead, Growth Marketer, SEO Specialist
        └── COO  (Operations)
              ├── Support Lead, Finance / Billing Analyst, Legal / Compliance Analyst
```

## Roster (32 agents)

**Model** follows task complexity, not title (model-allocation policy):
**`opus`** ×10 — leadership/judgment and every AADL gate owner, plus `cto` +
`security-lead` (permanently opus, Fable 5 decommissioned). **`sonnet`** ×19 — the
execution core. **`haiku`** ×3 — high-frequency, low-ambiguity work
(`seo-specialist`, `support-lead`, `tech-writer`). All 32 run as Claude Code
subagents (`.claude/agents/<role>.md`); there is no separate per-agent runtime
to configure.

### Governance (3) — wake-on-approval only
| Agent | Role key | Model | Reports to |
|---|---|---|---|
| Chairman of the Board | chairman | opus | — |
| Board Member | board-member | sonnet | — |
| CEO | ceo | opus | Chairman |

### Engineering (13) — CTO
| Agent | Role key | Model | Reports to |
|---|---|---|---|
| CTO | cto | opus | CEO |
| Backend EM | backend-em | opus | CTO |
| Frontend EM | frontend-em | opus | CTO |
| QA Lead | qa-lead | opus | CTO |
| SRE / DevOps Lead | sre-lead | opus | CTO |
| Security Lead | security-lead | opus | CTO |
| Backend Engineer 1 | backend-eng-1 | sonnet | Backend EM |
| Backend Engineer 2 | backend-eng-2 | sonnet | Backend EM |
| Frontend Engineer 1 | frontend-eng-1 | sonnet | Frontend EM |
| Frontend Engineer 2 | frontend-eng-2 | sonnet | Frontend EM |
| QA Engineer | qa-eng | sonnet | QA Lead |
| SRE Engineer | sre-eng | sonnet | SRE Lead |
| Security Engineer | security-eng | sonnet | Security Lead |

### Product (4) — CPO
| Agent | Role key | Model | Reports to |
|---|---|---|---|
| CPO | cpo | opus | CEO |
| Senior Product Manager | senior-pm | opus | CPO |
| Product Analyst | product-analyst | sonnet | CPO |
| Technical Writer | tech-writer | haiku | CPO |

### Design (4) — CDO
| Agent | Role key | Model | Reports to |
|---|---|---|---|
| CDO | cdo | sonnet | CEO |
| Design Lead | design-lead | sonnet | CDO |
| Product Designer | product-designer | sonnet | Design Lead |
| UX Researcher | ux-researcher | sonnet | Design Lead |

### Marketing (4) — CMO
| Agent | Role key | Model | Reports to |
|---|---|---|---|
| CMO | cmo | sonnet | CEO |
| Content Lead | content-lead | sonnet | CMO |
| Growth Marketer | growth-marketer | sonnet | CMO |
| SEO Specialist | seo-specialist | haiku | CMO |

### Operations (4) — COO
| Agent | Role key | Model | Reports to |
|---|---|---|---|
| COO | coo | sonnet | CEO |
| Support Lead | support-lead | haiku | COO |
| Finance / Billing Analyst | finance-analyst | sonnet | COO |
| Legal / Compliance Analyst | legal-analyst | sonnet | COO |

**Totals:** opus ×10 · sonnet ×19 · haiku ×3 = 32 (matches the model-allocation
SSOT).

## Dispatch: who runs in a wave

- **Wave-dispatched (29):** CEO + all 5 C-suite + all leads + all ICs.
  `/daslab-cycle` dispatches every actionable ticket owned by these roles;
  concurrency is harness-bounded (no policy parallel cap).
- **Wake-on-approval only (2):** Chairman, Board Member — they act on approvals
  / @-mentions, not on a wave dispatch.

## RACI for the active product (none currently)

There is no active product right now. When one exists, each agent's product
responsibilities live in their role overlay (`<dept>/agents/<role>/AGENTS.md`)
and the product repo's track→owner RACI map.

## Hiring / changing agents

New roles, retirements, and model-tier changes require **board approval** and a
PR that edits the model-allocation table, then a re-run of
`python3 scripts/gen_subagents.py`. The human operator approves in the main
session (there is no hire/approval API). Details in
[04-OPERATIONS.md](04-OPERATIONS.md).
