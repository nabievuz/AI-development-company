# AGENTS.md — DasLab Umbrella Spec

> Company-wide entry point. Every department overlay (`<dept>/AGENTS.md`) and role overlay (`<dept>/agents/<role-key>/AGENTS.md`) sits on top of this file.

## 0 — What DasLab is

DasLab (Dasturlash Laboratoriyasi, ticket prefix **DAS**) is an AI-native company of **32 agents** organized as a 4-level hierarchy: Board → CEO → Department Manager → IC.

> **Runtime:** DasLab runs on **Claude Code subagents** — platform (org-engine)
> tickets live in [`board/`](board/README.md) (project tickets live in the
> project's own board, `projects/<slug>/board-tickets/`), roles in
> `.claude/agents/` (generated from the overlays), orchestration via
> `/daslab-plan` + `/daslab-cycle`. See
> [`docs/06-CLAUDE-CODE-MODE.md`](docs/06-CLAUDE-CODE-MODE.md).

## 1 — Departments

| Dept | Charter | Manager |
|------|---------|---------|
| Governance | [`governance/CLAUDE.md`](governance/CLAUDE.md) | Chairman of the Board |
| Engineering | [`engineering/CLAUDE.md`](engineering/CLAUDE.md) | CTO |
| Product | [`product/CLAUDE.md`](product/CLAUDE.md) | CPO |
| Design | [`design/CLAUDE.md`](design/CLAUDE.md) | CDO |
| Marketing | [`marketing/CLAUDE.md`](marketing/CLAUDE.md) | CMO |
| Operations | [`operations/CLAUDE.md`](operations/CLAUDE.md) | COO |

## 2 — Precedence (binding)

When documents disagree, lower-precedence may add constraints but never relax them set higher up.

1. [`governance/charter.md`](governance/charter.md) — company charter.
2. Board-issued policy in `governance/` (security, compliance, hiring, conduct).
3. `<dept>/CLAUDE.md` — dept charter.
4. `<dept>/agents/<role>/AGENTS.md` — role overlay.
5. `<dept>/AGENTS.md` — runtime instructions.
6. This file.

## 3 — Methodology

DasLab runs as a **Hybrid**:

- **Operational layer = Kanban.** Pull-based; WIP = 1 task per wave per agent. Status enum: `backlog → todo → in_progress → blocked → in_review → done`. No sprints.
- **Governance layer = PRINCE2 / PMBOK.** Charter, RACI ([`governance/policies/raci.md`](governance/policies/raci.md)), RFC/ADR gates ([`engineering/RFCs/`](engineering/RFCs/), [`docs/adr/`](docs/adr/)), board approvals for hires/budget/strategy, weekly/monthly/quarterly cadence ([`governance/board-minutes/`](governance/board-minutes/)).
- **Engineering practice = Lean + selective XP.** Smallest reversible step, no silent blockers, TDD on engineering roles.

## 4 — Operating cadence

| Cadence | Audience | Artifact |
|---------|----------|----------|
| Per wave | Every agent | One pulled task, one comment, exit |
| Weekly | Board | `governance/board-minutes/<year>/<date>-weekly.md` |
| Monthly | Board + CEO | Strategic review entry in board-minutes |
| Quarterly | Board | Charter review (§6 of charter.md) |

Waves are operator-invoked (`/daslab-cycle`) — there is no timer. A role with nothing actionable in a wave is simply not dispatched.

## 5 — Where to start as a new agent

1. Read this file.
2. Read your dept `CLAUDE.md` (charter — what you may and may not decide).
3. Read your `<dept>/agents/<role-key>/AGENTS.md` (role-specific day-one priorities).
4. Read `<dept>/AGENTS.md` (wave protocol — applies to all agents identically).
5. **Recall memory:** call ArcRift `recall_context` with your task text (`project`
   = `daslab`, or `daslab-<project>` if project-specific — flat, NO slash; a "/"
   in a project name breaks ArcRift's URL routing) and read the returned
   `<ARCRIFT_retrieved_context>` before touching anything.
6. Follow the wave protocol: inbox → pick ONE → edit ticket file (set `status: in_progress`) → work → comment →
   **store memory** (`store_memory`: decision + why + result, same `project`) → exit.

## 6 — Hard rules (lifted from dept overlays — same everywhere)

- **Project placement law:** every project lives ONLY in `projects/<project-name>/`
  (a folder named after the project, created first). No project-specific files
  anywhere else — not in `docs/`, `scripts/`, dept repos, or external repos.
  Dept docs may mention a project by name but never host its content.
  One project = one folder, so retiring it is a single `rm -rf`.
  **This includes tickets:** a project's tickets live ONLY in the project's own
  board (`projects/<project-name>/board-tickets/`), never in the org
  `board/tickets/`. The org `board/tickets/` is reserved exclusively for
  DasLab-platform (org-engine) tickets; it carries no `project:` field
  (`scripts/board_lint.py` enforces this). Ticket refs in prose (`DAS-12`) that
  resolve to `board/tickets/DAS-12-*.md` are org-engine tickets.
- **AI Agent Lifecycle law:** every project shipping agentic AI follows the
  six-stage lifecycle (Planning → Design → Development → Testing → Deployment
  → Maintenance) per [`governance/policies/ai-agent-lifecycle.md`](governance/policies/ai-agent-lifecycle.md).
  Stage-gated epics, no stage skipped, gates logged in the project README.
  Production launch with GATE-5 open is forbidden.
- **ArcRift memory law:** persistent memory lives in ArcRift (MCP server
  `ArcRift`). `recall_context` at task start, `store_memory` at task end, scoped
  to `project = daslab` (or `daslab-<project>`, flat — no slash). Never cross project scopes;
  `prune_memory` corrects stale facts. (Full rule: `CLAUDE.md` QONUN — Persistent Memory Law.)
- **Founder-approved goal queue law:** a new project cannot produce board
  tickets until DasLab asks the Founder at least 10 discovery questions, enriches
  the answers with current global research, writes
  `projects/<project>/APPROVED-GOAL-QUEUE.md`, and receives explicit Founder
  approval for the queue. Agents may auto-plan only from approved queue items;
  they never invent new goals to stay busy.
- Always append a `## Log` entry before exiting a ticket — who, what, why. Never a silent edit.
- Set `parent:` + `goal:` on every subtask you create.
- Never cancel cross-team tasks — reassign to your manager.
- Ticket refs in prose use file-relative format: `DAS-12` resolves to `board/tickets/DAS-12-*.md`; never bare identifiers.
- **Touching a git repo?** One issue = one branch = one PR; never commit to `main`;
  isolate concurrent work in a git worktree; push + open a PR before `in_review`;
  `done` requires a merged PR with green CI. (Full rules: `engineering/AGENTS.md` §2.)

## 7 — Identity check at every wake

You must be operating in the repo root (or a worktree of it): verify that
`board/tickets/` exists relative to your working directory.
If your prompt names a ticket that does not exist under `board/tickets/`,
**stop** — you were spawned with stale context. (Project tickets live in the
project's own board, `projects/<slug>/board-tickets/` — a project-context agent
verifies that path instead of the org `board/tickets/`.)
