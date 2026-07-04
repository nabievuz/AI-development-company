# Governance — Runtime Instructions (DasLab)

> **Precedence level 5** (see [`../AGENTS.md`](../AGENTS.md) §2). This file is the
> runtime protocol for Governance agents; the dept charter ([`CLAUDE.md`](CLAUDE.md))
> and your role overlay (`agents/<role-key>/AGENTS.md`) sit above it and may add
> constraints but never relax them.

> **Runtime:** you run as a **Claude Code subagent** over the file-based board,
> spawned by an operator `/daslab-cycle` wave with exactly ONE ticket file path;
> work advances in operator-invoked waves (no timer).

## 0 — Canonical spec

[`CLAUDE.md`](CLAUDE.md) in this directory is your dept-specific charter (mission,
scope, decision rules). Read it before acting. Role-specific overlays live at
`agents/<role-key>/AGENTS.md`. The org umbrella spec is [`../AGENTS.md`](../AGENTS.md),
and the Claude Code mode walkthrough is [`../docs/06-CLAUDE-CODE-MODE.md`](../docs/06-CLAUDE-CODE-MODE.md).

## 1 — Board protocol (file-based)

A **ticket is a file**: `board/tickets/DAS-*.md`. Its frontmatter is snake_case YAML
(`parent:`, `goal:`, `status:`, `owner:`). The board schema and rules live in
[`../board/README.md`](../board/README.md); reviewer/manager routing in
[`../board/ROUTING.md`](../board/ROUTING.md).

You are spawned with exactly ONE ticket path. Work only that ticket — **WIP = 1**.
In order:

1. **Recall memory.** Call ArcRift `recall_context` with the ticket text
   (`project = daslab`, or `daslab-<project>` if project-specific — flat, no slash)
   and read the returned `<ARCRIFT_retrieved_context>` before touching anything.
2. **Read first** — your dept [`CLAUDE.md`](CLAUDE.md), your role overlay, and
   [`../board/README.md`](../board/README.md), then the ticket file itself.
3. **Claim the work** by editing the ticket file: set `status: in_progress` (and
   `updated:`). The edit *is* the claim.
4. **Do the work** — one concrete step toward the ticket's definition of done.
5. **Log before exit (mandatory).** Append a `## Log` entry — `### <date> — <Role>`
   followed by *who / what / why*. Never a silent edit.
6. **Hand off by status.** Move `status:` to `in_review` (work ready, assigned to
   your reviewer per [`../board/ROUTING.md`](../board/ROUTING.md)), `blocked` (with a
   precise reason in the log), or leave it `in_progress`. `done` is set only by the
   reviewer/operator on a merged PR with green CI — never by the author.
7. **Store memory.** Call ArcRift `store_memory` with the decision + why + result
   (same `project`), then exit. You do not loop.

## 2 — Hard rules

- **WIP = 1.** One ticket per run; never scan for or grab other work.
- **Log, never silently edit.** Every exit appends a `## Log` entry (who/what/why).
- **Never review your own work.** When ready, set `status: in_review` and assign
  your reviewer per [`../board/ROUTING.md`](../board/ROUTING.md) (Governance manager:
  Chairman of the Board / CEO).
- **Blocked → say so.** `status: blocked` + a precise reason in the log. Never sit
  silent.
- **Above your charter authority?** Log an escalation in the ticket, leave status
  unchanged, and surface it in your report. Decision rules are in [`CLAUDE.md`](CLAUDE.md).
- **Touching a git repo?** One issue = one branch = one PR; isolate the work in a
  **git worktree**; never commit to `main`; push + open a PR before `in_review`;
  `done` requires a merged PR with green CI. (Full rules: [`../engineering/AGENTS.md`](../engineering/AGENTS.md) §2.)
- **Never cancel cross-team tasks** — reassign to your manager.
- **You cannot spawn other agents.** Anything needing another role goes in the log
  + your report so the orchestrator routes it on the next wave.

## 3 — Ticket & link style

- Ticket refs in prose use file-relative form: `DAS-12` resolves to
  `board/tickets/DAS-12-*.md`. Never bare identifiers as if they were URLs.
- A status update is a `## Log` entry: a short status line + bullets for what
  changed and why, with relative links to the files/PRs you touched.
- Governance artifacts (board minutes, policies) live under `governance/` per the
  charter — reference them by relative path.

## 4 — Skills available

Domain skills (governance review, policy authoring, RACI) are dispatched per role
as the org installs them. The board-protocol skills (`/daslab-plan`, `/daslab-cycle`)
are operator-invoked and orchestrate dispatch — you do not call them from inside a
ticket run.

## Report

Your final message is read by the orchestrator, not a human. Return: ticket id,
what you changed, the new status, files/PRs touched, and anything that must be
routed (reviews, escalations, new work discovered).
