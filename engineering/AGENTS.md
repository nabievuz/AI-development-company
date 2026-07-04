# Engineering — Runtime Instructions (DasLab)

> **Precedence level 5** (see [`../AGENTS.md`](../AGENTS.md) §2). This file is the
> runtime protocol for Engineering agents; the dept charter ([`CLAUDE.md`](CLAUDE.md))
> and your role overlay (`agents/<role-key>/AGENTS.md`) sit above it and may add
> constraints but never relax them.

> **Runtime:** You run as a **Claude Code subagent**, spawned by an operator
> wave (`/daslab-cycle`) with exactly ONE ticket file path. There is **no HTTP
> API and no timer** — work is files in `git`, and dispatch is operator-invoked
> waves, not a clock.

## 0 — Canonical spec

[`CLAUDE.md`](CLAUDE.md) in this directory is your dept-specific charter (mission,
scope, decision rules). Read it before acting. Role-specific overlays live at
`agents/<role-key>/AGENTS.md`. The org umbrella spec is [`../AGENTS.md`](../AGENTS.md),
and the Claude Code runtime walkthrough is [`../docs/06-CLAUDE-CODE-MODE.md`](../docs/06-CLAUDE-CODE-MODE.md).

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
   `updated:`). There is no separate claim call — the edit *is* the claim.
4. **Read the current code state BEFORE implementing** — a ticket may list work
   that is already done; build only the genuine gap. Then do the work in an
   **isolated git worktree** off fresh `origin/main`, one branch per issue
   (`feat/das-<id>-<slug>`). NEVER commit to `main`, NEVER share a worktree with
   another agent. Run the **exact** gate CI runs (e.g. `pnpm lint && pnpm typecheck
   && pnpm test`) — not a lighter local variant. See skill `using-git-worktrees`.
5. **Push the branch and open a PR** (`finishing-a-development-branch` /
   `requesting-code-review`). Then set `status: in_review` on the ticket, **assigned
   to your reviewer** per [`../board/ROUTING.md`](../board/ROUTING.md) (your EM / QA
   Lead / Design Lead — never leave it assigned to yourself), with the PR URL in the
   log. Code is **not `done` until the PR is merged with green GitHub CI** — only the
   reviewer/operator sets `done`.
6. **Log before exit (mandatory).** Append a `## Log` entry — `### <date> — <Role>`
   followed by *who / what / why + the PR URL*. Never a silent edit.
7. **Store memory.** Call ArcRift `store_memory` with the decision + why + result
   (same `project`), then exit. You do not loop.

## 2 — Hard rules

- **WIP = 1.** One ticket per run; never scan for or grab other work.
- **Log, never silently edit.** Every exit appends a `## Log` entry (who/what/why).
- **Never review your own work.** When ready, set `status: in_review` and assign
  your reviewer per [`../board/ROUTING.md`](../board/ROUTING.md) (Engineering manager:
  CTO).
- **Blocked → say so.** `status: blocked` + a precise reason in the log. Never sit
  silent.
- **Above your charter authority?** Log an escalation in the ticket, leave status
  unchanged, and surface it in your report.
- **You cannot spawn other agents.** Anything needing another role goes in the log
  + your report so the orchestrator routes it on the next wave.

**Git & PR discipline (non-negotiable — these caused real incidents):**

- **One issue = one branch = one PR.** Never bundle tickets on a branch.
- **Never commit to `main`** (local or origin). `main` changes only via merged PR.
- **Isolate concurrent work in a git worktree** off fresh `origin/main`. Two agents
  in one worktree corrupt each other's branches — a real incident bundled 3 tickets
  into one conflicting PR.
- **Push + open a PR before `in_review`.** Local-only commits don't count.
- **CI green is the gate.** Never `done` until the PR's GitHub CI passes — some
  suites (DB integration tests) skip locally and only run in CI.
- **Read before you build.** Inspect the repo's current state first; don't
  re-implement what already exists.
- Full protocol: skill `using-git-worktrees` + [`../board/README.md`](../board/README.md).

## 3 — Ticket & link style

- Ticket refs in prose use file-relative form: `DAS-12` resolves to
  `board/tickets/DAS-12-*.md`. Never bare identifiers as if they were URLs.
- A status update is a `## Log` entry: a short status line + bullets for what
  changed and why, with the PR URL and relative links to the files you touched.
- Engineering artifacts (RFCs, ADRs, runbooks) live under `engineering/` per the
  charter — reference them by relative path.

## 4 — Skills available

Use them — don't just have them. Engineering agents carry:

- `using-git-worktrees` — isolate every issue's work (mandatory under concurrency).
- `test-driven-development` — red → green → refactor (tests first, always).
- `verification-before-completion` — evidence (CI green) before claiming done.
- `finishing-a-development-branch` / `requesting-code-review` — branch → push → PR.
- `systematic-debugging` — root-cause before patching.
- `subagent-driven-development` / `dispatching-parallel-agents` (EMs) — fan-out by
  file-ownership in worktrees.

Invoking the relevant skill is not optional — the git/verify skills above exist
precisely to prevent the incidents listed in §2.

## Report

Your final message is read by the orchestrator, not a human. Return: ticket id,
what you changed, the new status, files/branches/PRs touched, and anything that
must be routed (reviews, escalations, new work discovered).
