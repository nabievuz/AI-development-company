# 01 — DasLab Overview

> What DasLab is, how it works, and why it's built this way. Read this first.

## What DasLab is

**DasLab** (*Dasturlash Laboratoriyasi*, "Programming Laboratory") is an **AI-native
software company** — a complete org of **32 AI agents** that plan, build, review, ship,
and operate real software products with minimal human input. It runs as **Claude Code
subagent sessions** over a file-based board (`board/tickets/*.md`), dispatched in
operator-invoked waves by [`/daslab-cycle`](06-CLAUDE-CODE-MODE.md).

- **Ticket prefix:** `DAS`
- **Board:** `board/tickets/DAS-*.md` (snake_case YAML frontmatter)

It is not a single agent with tools — it is an **organization**: a board, a CEO, five
C-suite department heads, team leads, and individual contributors, each a separate
Claude Code subagent with its own role, instructions, and reporting line.

## How it works (the wave)

DasLab runs on **operator-invoked waves** — there is no timer. The operator types
`/daslab-cycle` and one wave runs: the orchestrator triages the board, dispatches
every actionable role subagent in parallel, collects their results, and reports.
Concurrency is bounded only by the Claude Code harness, AADL gate order, and the
same-repo-area correctness guard (one ticket per repo zone per wave) — not by a
fixed clock or a policy cap.

```
        ┌─────────────────────────────────────────────┐
        │  Operator sets a goal (/daslab-plan) →         │
        │  tickets → its board (project or platform)     │
        └───────────────────────┬─────────────────────┘
                                 │  operator runs /daslab-cycle
                    ┌────────────▼────────────┐
                    │   One wave (on demand)    │  triage board → find
                    │   triage + dispatch       │  every actionable ticket
                    └────────────┬────────────┘
                                 │ dispatches in parallel
              ┌──────────────────┼──────────────────┐
        ┌─────▼─────┐      ┌──────▼──────┐     ┌─────▼─────┐
        │ C-suite   │      │   Leads     │     │   ICs     │
        │ route     │─────▶│ break down  │────▶│ do work,  │  each subagent does
        │           │      │             │     │ report    │  its ticket, then exits
        └───────────┘      └─────────────┘     └─────┬─────┘
                                                     │ in_review
                                              ┌──────▼──────┐
                                              │ Quality gates│  EM + QA + Security
                                              │ → done       │  → merged
                                              └─────────────┘
```

Each subagent runs once per wave: **read its ticket → do the work → report → exit.**
**WIP = 1 ticket per role per wave.** Nothing actionable for a role → it isn't
dispatched. Work advances only when the operator runs the next wave.

## The hierarchy (4 levels)

```
Board (Chairman + Board Member)        ← governance, approvals; wake-on-demand only
  └── CEO                              ← accountable for the whole company goal
        ├── CTO   (Engineering)
        ├── CPO   (Product)
        ├── CDO   (Design)
        ├── CMO   (Marketing)
        └── COO   (Operations)
              └── Leads → ICs          ← the people who do the work
```

Full roster, budgets, and reporting lines: [02-ORG.md](02-ORG.md).

## Methodology — a deliberate hybrid

DasLab blends three disciplines (rationale in [`../AGENTS.md`](../AGENTS.md) §3):

| Layer | Method | What it means |
|---|---|---|
| **Operational** | **Kanban** | Pull-based, WIP=1, no sprints. Status: `backlog → todo → in_progress → blocked → in_review → done`. |
| **Governance** | **PRINCE2 / PMBOK** | Charter, RACI, RFC/ADR gates, board approvals for hires/budget/strategy, weekly/monthly/quarterly cadence. |
| **Engineering** | **Lean + selective XP** | Smallest reversible step, no silent blockers, TDD on engineering roles. |

## Operating cadence

| Cadence | Audience | Artifact |
|---|---|---|
| Per wave | Every dispatched agent | one ticket advanced + one report |
| Weekly | Board | `governance/board-minutes/<year>/<date>-weekly.md` |
| Monthly | Board + CEO | strategic review in board-minutes |
| Quarterly | Board | charter review (`governance/charter.md` §6) |

There is no timer: waves run when the operator invokes `/daslab-cycle`, and a single
wave may dispatch every actionable ticket at once.

## How work is structured

```
Goal  →  Epic (one per project track)  →  Ticket (one deliverable)  →  Subtask (PR-sized)
```

Every ticket carries snake_case YAML frontmatter — `parent:`, `goal:`, `status:`,
`owner:` — plus acceptance criteria. No orphan tickets. Decomposition rules live
in the [`/daslab-plan`](../.claude/skills/daslab-plan/SKILL.md) skill.

## What DasLab is building

There is currently **no active product**. The org stands ready to take on the next
Founder-approved, research-backed goal queue via `/daslab-plan`. See
[03-PROJECTS.md](03-PROJECTS.md) for past project history.

## Where to go next

- **Operate the org** (start/stop, monitor, hire) → [04-OPERATIONS.md](04-OPERATIONS.md)
- **See who's in it** → [02-ORG.md](02-ORG.md)
- **See what it's building** → [03-PROJECTS.md](03-PROJECTS.md)
- **Understand the scripts** → [05-SCRIPTS.md](05-SCRIPTS.md)
- **Read the binding agent spec** → [`../AGENTS.md`](../AGENTS.md)
