# DasLab — Operator User Guide

> **DasLab** (*Dasturlash Laboratoriyasi*, ticket prefix **DAS**) is an operating
> system for a **32-agent AI-native software organization**. Every role — from
> Chairman to QA Engineer — is a Claude Code subagent with a written charter,
> dispatched against a **file-based board** under a six-stage AI-Agent Development
> Lifecycle (AADL).
>
> **Runtime:** a single Claude Code session at the repo root that orchestrates the
> org as on-demand subagents. There is **no server, no API, no dashboard, and no
> background timer**. Work advances only when you invoke a wave. (See
> [06-CLAUDE-CODE-MODE.md](06-CLAUDE-CODE-MODE.md).)

This guide is for the **human operator** who drives the org. It covers what DasLab
is, how to boot it, the board model, the three orchestration commands, the
Founder approval flow, where the org's source of truth lives, and how to diagnose
a broken environment.

---

## 1. What DasLab is

DasLab is a self-contained, reproducible org-in-a-repo. A fresh `git clone` boots
the whole company with zero missing pieces. The model:

- **32 agents, 4 levels.** `Board (Chairman + Board Member) → CEO → Department
  Manager → IC`, across six departments: Governance, Engineering, Product,
  Design, Marketing, Operations.
- **File-based board.** Work items are markdown files in `board/tickets/` — plain
  files, no database. ([schema](../board/README.md))
- **Subagent roles.** Each role is a generated subagent definition in
  `.claude/agents/<role-key>.md`, produced by `scripts/gen_subagents.py` from the
  per-role overlays (`<dept>/agents/<role-key>/AGENTS.md`) — the overlays are the
  single source of truth for each role's mission.
- **Operator-invoked waves.** Three skills move work: `/daslab-plan`,
  `/daslab-cycle`, and `/daslab-run`. Nothing runs unless you invoke it.
- **You hold the keys.** Board approvals, hires, budget, and production go-live
  stay with the human operator in the main session — never auto-approved.

---

## 2. Prerequisites

| Need | Why |
|---|---|
| **Claude Code CLI** (`claude` on `PATH`) | The runtime — every wave runs inside a session. |
| **Python ≥ 3.10** | Bootstrap, doctor, and the validator scripts. |
| **git** | One issue = one branch = one PR; worktree-per-ticket isolation. |

**Optional (persistent memory layer — degrades gracefully if absent):**

- **ArcRift** MCP server (long-term memory across sessions).
- **Ollama** running `nomic-embed-text` (embeddings for memory recall).

If the optional layer is missing, `doctor.py` prints `WARN` and memory recall/store
become best-effort — the org still boots and runs.

---

## 3. First run

Three commands and you are live:

```bash
git clone https://github.com/nabievuz/daslab.git && cd daslab
python3 scripts/bootstrap.py     # idempotent first-run: creates projects/, regenerates the 32 agent shims
python3 scripts/doctor.py        # preflight — REQUIRED checks must all PASS (ArcRift/Ollama are OPTIONAL → WARN)
claude                           # open a Claude Code session at the repo root
```

- `bootstrap.py` resolves the repo root at runtime, ensures the gitignored
  `projects/` workspace exists, regenerates `.claude/agents/*` from the org tree,
  and reports the environment via `doctor.py`. Safe to re-run — every step is
  idempotent.
- `doctor.py` exits `0` when every REQUIRED check passes (Claude Code CLI, Python
  ≥ 3.10, git, repo-root resolution, `projects/`). OPTIONAL memory-layer failures
  print `WARN` and do not block.

Then, inside the `claude` session, drive the org with the commands in §5.

---

## 4. The board model

One markdown file in `board/tickets/` = one ticket. Filename:
`DAS-<n>-<slug>.md`, ids strictly increasing (next = max existing + 1; an empty
board starts at DAS-1001). Frontmatter is **snake_case YAML**:

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

**Status enum (the only valid values):**
`backlog → todo → in_progress → blocked → in_review → done`.

**Ticket rules that matter to you as operator:**

- **WIP = 1.** A subagent works only the one ticket named in its prompt.
- **Append-only log.** Every state change appends a `## Log` entry (who, what,
  why) — never a silent edit. The log is your audit trail.
- **Review goes to the manager.** `in_review` switches `assignee` to the reviewer
  (the author's manager per `board/ROUTING.md`) — an agent never reviews its own
  work.
- **`done` for engineering** = merged PR with green CI.
- **`blocked`** requires a precise reason in the log. External-dependency blocks
  (RAHMAT, UZINFOCOM, IKPU, tax, legal entity) are tracked, never auto-dispatched.
- **No orphans.** Every subtask carries `parent:` + `goal:`.

To inspect the board, read the files under `board/tickets/`, or just ask the
session in plain language. The full schema and routing rules are in
[`board/README.md`](../board/README.md) and [`board/ROUTING.md`](../board/ROUTING.md).

---

## 5. Driving the org — the three commands

You operate DasLab entirely through three skills invoked inside the `claude`
session. Nothing runs on a timer; each command is one explicit action.

| You want | Command |
|---|---|
| Start a new project / decompose a goal into tickets | `/daslab-plan "<goal>"` |
| Run one work wave (dispatch every actionable ticket) | `/daslab-cycle` |
| Run a smaller, bounded wave of at most N tickets | `/daslab-cycle 10` |
| Drain the Founder-approved goal queue end to end | `/daslab-run` |
| Inspect the board | read `board/tickets/`, or just ask |

### `/daslab-plan "<goal>"`

Decomposes a goal into board tickets. For a **new project** or an unclear product
goal, it first runs the **Founder Discovery Gate** (see §6) — it does not create
tickets immediately. Once a goal is Founder-approved, it produces the hierarchy
`Goal → Epic → Ticket`: epics get `status: backlog` and a lead/manager owner;
child tickets are PR-sized with concrete acceptance criteria, `status: todo`, and
an IC assignee per RACI. For AI-agent goals the AADL law applies — exactly one
epic per lifecycle stage, with each epic's acceptance criteria being that stage's
GATE checklist.

### `/daslab-cycle [N]`

Runs **one work wave**. It triages the board (routes unassigned tickets per RACI,
reroutes any self-reviews), selects actionable tickets (priority order:
`p0 → in_review → in_progress → todo`; one ticket per role; no two engineering
tickets in the same repo area), dispatches the role subagents **in parallel**,
collects the results, verifies the ticket files actually changed, and reports.

There is **no policy cap** on wave size — `/daslab-cycle` may dispatch every
actionable ticket; real concurrency is bounded only by the Claude Code harness,
AADL gate order, same-repo-area correctness guards, and git worktree isolation.
The optional `N` is just a deliberate smaller-wave bound. Stage-gated tickets are
skipped while the previous AADL gate is still open.

### `/daslab-run`

The operator-invoked **supervisor**. It plans the next Founder-approved queue item
when the board is empty, then repeats `/daslab-cycle` waves until the tickets drain
or a real stop condition appears (a blocker, a missing Founder approval, or no
approved queue left). It is a supervisor you launch — not a background timer or a
night script.

---

## 6. The Founder discovery gate and approved goal queue

A new project does **not** become board tickets the moment you describe it. It
first passes a discovery gate so the org never invents work for itself:

1. **Discovery.** When `/daslab-plan` sees a new project or an unclear product
   goal, it asks the Founder **at least 10 questions** (market, users, scope,
   constraints, success criteria) before drafting anything — unless the Founder
   explicitly answers, declines, or waives them.
2. **Research.** It then does current global research with source links —
   market, competitors, regulatory/compliance, technical architecture,
   pricing/unit-economics, channel/SEO, and risks.
3. **Queue file.** The result is written **only inside the project folder**:
   `projects/<project-name>/APPROVED-GOAL-QUEUE.md` (plus any planning docs). This
   respects the project-placement law — everything for a project lives under
   `projects/<name>/` and nowhere else.
4. **Founder approval.** No board tickets are created until the Founder explicitly
   approves the queue (an explicit signal such as `APPROVED:` or `TASDIQLANDI:`).
   `/daslab-cycle` and `/daslab-run` only plan from this approved queue — they
   never fabricate a goal to keep agents busy.

`projects/` is gitignored; each project manages its own git repo.

---

## 7. Human approvals — never auto-approve

A set of decisions stays with you, the human operator, in the main session. They
are **never auto-approved** by an agent:

- **Board approvals** — charter rulings, policy changes, strategy sign-off.
- **Hires / retires** — adding or removing a role (which then requires regenerating
  the agent shims, §8).
- **Budget** — over-limit spend is a board decision, not an agent preference.
- **Production go-live** — no release ships with AADL GATE-5 open.

Agents surface these for your decision and leave the work in `blocked` or
`in_review` until you act; they do not push past the gate. An agent also never
upgrades its own model — hard work escalates up the ladder to the author's manager
(ultimately CTO/CEO) per [`board/ROUTING.md`](../board/ROUTING.md).

---

## 8. Where the org lives — roles, policies, skills

| What | Where |
|---|---|
| Umbrella spec (binding, read-first for agents) | [`../AGENTS.md`](../AGENTS.md) |
| Claude Code project instructions (the QONUN laws) | [`../CLAUDE.md`](../CLAUDE.md) |
| Company charter | [`../governance/charter.md`](../governance/charter.md) |
| Model allocation policy (opus ×10 · sonnet ×19 · haiku ×3) | [`../governance/policies/model-allocation.md`](../governance/policies/model-allocation.md) |
| AI-Agent Development Lifecycle (AADL) policy | [`../governance/policies/ai-agent-lifecycle.md`](../governance/policies/ai-agent-lifecycle.md) |
| RACI decision matrix | [`../governance/policies/raci.md`](../governance/policies/raci.md) |
| Department charters | `engineering/CLAUDE.md`, `product/CLAUDE.md`, `design/CLAUDE.md`, `marketing/CLAUDE.md`, `operations/CLAUDE.md` |
| Role overlays (a role's mission source of truth) | `<dept>/agents/<role-key>/AGENTS.md` |
| Generated subagent shims (do **not** hand-edit) | `.claude/agents/*.md` |
| Orchestration skills | [`/daslab-plan`](../.claude/skills/daslab-plan/SKILL.md) + [`/daslab-cycle`](../.claude/skills/daslab-cycle/SKILL.md) |
| The full 32-agent roster | [AGENT-ROSTER.md](AGENT-ROSTER.md) |
| Org chart and reporting lines | [02-ORG.md](02-ORG.md) |
| Script inventory | [05-SCRIPTS.md](05-SCRIPTS.md) |
| A worked end-to-end example | [EXAMPLE-RUN.md](EXAMPLE-RUN.md) |

**Precedence (when documents disagree)** — lower levels may *add* constraints but
never relax higher ones: charter → board policy → dept charter → role overlay →
dept runtime instructions → root [`AGENTS.md`](../AGENTS.md).

**Maintenance note.** If you edit a role overlay or hire/retire a role, regenerate
the shims so `.claude/agents/*` and `board/ROUTING.md` stay in sync with the
overlays:

```bash
python3 scripts/gen_subagents.py
```

Never hand-edit `.claude/agents/*` or `board/ROUTING.md` — the overlays plus
[`../governance/policies/model-allocation.md`](../governance/policies/model-allocation.md)
are the single source of truth.

---

## 9. Troubleshooting / doctor

Start any debugging with the environment preflight:

```bash
python3 scripts/doctor.py          # PASS/WARN/FAIL table
python3 scripts/doctor.py --json   # machine-readable
```

| Symptom | Check |
|---|---|
| A command or `claude` is "not found" | `doctor.py` REQUIRED rows — Claude Code CLI, Python ≥ 3.10, git must all be PASS. |
| `projects/` missing / agents look stale | Re-run `python3 scripts/bootstrap.py` (idempotent). |
| Memory recall/store not working | The optional ArcRift + Ollama rows are `WARN` — wire them per `governance/policies/memory-modes.md`, or run without persistent memory. |
| A ticket won't dispatch | It may be `blocked` (read its `## Log`), behind an open AADL gate, or waiting on a human approval (§7). |
| Agent shims drift from overlays | `python3 scripts/gen_subagents.py`, then commit the regenerated files. |

The repo also ships validators (`board_lint.py`, `check_links.py`,
`check_gates.py`, and more) and the release scorer `diagnostics.py`. See
[05-SCRIPTS.md](05-SCRIPTS.md) for the full inventory and run order, and
[06-CLAUDE-CODE-MODE.md](06-CLAUDE-CODE-MODE.md) for the canonical runtime
description.

---

*One issue = one branch = one PR; nothing merges to `main` without a green CI run.
Welcome aboard — invoke a wave and the org goes to work.*
