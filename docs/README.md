# DasLab — Documentation Hub

> **Start here.** This is the master index for the entire DasLab organization:
> what it is, how it runs, who's in it, what it's building, and how to operate it.
>
> Ticket prefix **DAS** · License **Apache-2.0**
> Runtime: a Claude Code session over `board/` files — no server, no API.

DasLab (*Dasturlash Laboratoriyasi*) is an **AI-native software company of 32 agents**
that runs as a Claude Code session orchestrating the org as subagents over the
file-based `board/` and ships real products. This hub explains the whole system end
to end. (Runtime: [06-CLAUDE-CODE-MODE.md](06-CLAUDE-CODE-MODE.md).)

---

## 📚 The documentation set

| Doc | What's in it |
|---|---|
| **[01-OVERVIEW.md](01-OVERVIEW.md)** | What DasLab is, how it works (Claude Code subagent waves, hybrid methodology), the big picture. **Read this first.** |
| **[02-ORG.md](02-ORG.md)** | Org chart, the 32-agent roster (roles, models, reporting lines), and where the roster lives. |
| **[03-PROJECTS.md](03-PROJECTS.md)** | Products DasLab builds. Active: **none currently**. Past projects. |
| **[04-OPERATIONS.md](04-OPERATIONS.md)** | **Human operator runbook** — how to run a wave, monitor the board, and what stays a human approval. |
| **[05-SCRIPTS.md](05-SCRIPTS.md)** | Inventory of every script in `scripts/` — purpose, when to run, run order. |
| **[06-CLAUDE-CODE-MODE.md](06-CLAUDE-CODE-MODE.md)** | **How the runtime works** — the org runs on Claude Code subagents over the file-based `board/` (`/daslab-plan`, `/daslab-cycle`). **Operators start here.** |
| **[USER-GUIDE.md](USER-GUIDE.md)** | Operator user guide. |
| **[ARCHITECTURE.md](ARCHITECTURE.md)** | **System design** — components, the dispatch/wave model, worktree concurrency, enforcement gates, model allocation, and the ArcRift loop; includes architecture + wave diagrams. |
| **[USAGE.md](USAGE.md)** | **End-to-end operator guide** — bootstrap, drive the org, plan a new project, and the four QONUN laws in practice. |

**Authoritative agent spec (binding):** [`../AGENTS.md`](../AGENTS.md) — the umbrella
instructions every agent reads at wake-up. This hub *describes* the org for humans;
`AGENTS.md` + the department charters *govern* the agents.

**Orchestration skills:** [`/daslab-plan`](../.claude/skills/daslab-plan/SKILL.md) +
[`/daslab-cycle`](../.claude/skills/daslab-cycle/SKILL.md) — how the org decomposes
goals into tickets and dispatches gate-enforced waves.

---

## 🗂 Repository layout

```
daslab/
├── AGENTS.md                  # Umbrella spec (binding, read-first for agents)
├── docs/                      # ← YOU ARE HERE — human documentation hub
│   ├── README.md              #   this index
│   ├── ARCHITECTURE.md        #   system design (+ diagrams)
│   ├── USAGE.md               #   end-to-end operator guide
│   ├── 01-OVERVIEW.md … 07-CONTEXT-PACK.md
│   └── adr/                   #   Architecture Decision Records
├── governance/                # Board: charter, policies (RACI), board-minutes. CEO + Chairman + Board Member
├── engineering/               # CTO + EMs + ICs. Dept charter, role overlays, RFCs, skills
├── product/                   # CPO + Senior PM + Analyst + Tech Writer. Roadmap, specs
├── design/                    # CDO + Design Lead + Product Designer + UX Researcher. Tokens, components
├── marketing/                 # CMO + Content Lead + SEO + Growth. Brand, calendars, campaigns
├── operations/                # COO + Finance + Legal + Support. Compliance, vendors, burn, SLA
├── scripts/                   # Bootstrap + validators (see 05-SCRIPTS.md)
├── .claude/                   # Generated subagent shims + orchestration skills (/daslab-plan, /daslab-cycle)
└── projects/                  # Per-project workspaces — gitignored (each manages its own git)
```

> **Note:** each `<dept>/` is a tracked directory in this repository (the six department
> trees are part of the tree) and an agent working directory.
> There is currently no active product (see [03-PROJECTS.md](03-PROJECTS.md)).

---

## 🧭 How agent instructions compose (precedence)

Every agent reads these at wake-up; lower precedence may **add** constraints, never relax them:

1. [`../governance/charter.md`](../governance/charter.md) — company charter
2. Board policy in [`../governance/policies/`](../governance/policies/) (e.g. [RACI](../governance/policies/raci.md))
3. `<dept>/CLAUDE.md` — department charter
4. `<dept>/agents/<role>/AGENTS.md` — role overlay
5. `<dept>/AGENTS.md` — department runtime instructions
6. [`../AGENTS.md`](../AGENTS.md) — umbrella

Department charters: [Governance](../governance/CLAUDE.md) · [Engineering](../engineering/CLAUDE.md) · [Product](../product/CLAUDE.md) · [Design](../design/CLAUDE.md) · [Marketing](../marketing/CLAUDE.md) · [Operations](../operations/CLAUDE.md)

---

## ⚡ Quick facts

- **32 agents**, 4-level hierarchy: Board → CEO → Dept Manager (C-suite) → Lead → IC.
- **Runtime:** Claude Code subagents over the file-based `board/`. See [02-ORG.md](02-ORG.md).
- **Cadence:** operator-invoked `/daslab-cycle` waves — no timer. Each wave dispatches every actionable ticket (concurrency is harness-bounded).
- **Status enum:** `backlog → todo → in_progress → blocked → in_review → done`.
- **Budget:** $200,000/mo company cap (utilization ~0% — essentially free at current scale).
- **Active product:** none currently.

For the binding rules and the live numbers, follow the links above.
