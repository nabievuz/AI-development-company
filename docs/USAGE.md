# DasLab — Usage (end-to-end operator guide)

> How to drive the whole organization from a clean clone to shipped work. This is
> the practical, command-by-command companion to the reference docs: the runtime is
> explained in [06-CLAUDE-CODE-MODE.md](06-CLAUDE-CODE-MODE.md), the human runbook in
> [04-OPERATIONS.md](04-OPERATIONS.md), and the broader operator manual in
> [USER-GUIDE.md](USER-GUIDE.md). Start here when you just want to *run it*.

DasLab is an AI-native software company expressed as a repository: a board, a CEO, a
C-suite, leads, and individual contributors — each a Claude Code subagent with a
written charter. There is **no server, no API, no dashboard, and no background
timer**. Work advances only when you, the operator, invoke a wave from a Claude Code
session at the repo root. This guide walks the full path: boot the org, plan a goal,
run waves, read the output, and understand the rules that govern every working day.

---

## 1. Prerequisites

| Need | Why |
|---|---|
| **Claude Code CLI** (`claude` on `PATH`) | The runtime — every wave runs inside a session. |
| **Python ≥ 3.10** | `bootstrap.py`, `doctor.py`, and the validator/scorer scripts. |
| **git** | One issue = one branch = one PR; worktree-per-ticket isolation. |

**Optional — the persistent-memory layer (degrades gracefully if absent):**

- **ArcRift** MCP server — long-term memory across sessions (wired in
  [`../.mcp.json`](../.mcp.json) under the name `ArcRift`).
- **Ollama** running `nomic-embed-text` — local embeddings for memory recall.

If the optional layer is missing, `doctor.py` reports `WARN` (never `FAIL`): the org
still boots and runs, and memory recall/store become best-effort. See §8.

---

## 2. Bootstrap and doctor (once per clone)

Two commands set up a fresh clone, in this exact order (the ordering is itself
CI-enforced by `scripts/check_quickstart.py`):

```bash
git clone https://github.com/nabievuz/daslab.git && cd daslab

# 1. Idempotent first-run setup: resolve the repo root, create the gitignored
#    projects/ workspace, and regenerate the 32 agent shims from the org tree.
python3 scripts/bootstrap.py

# 2. Environment preflight. REQUIRED checks (Claude Code, Python, git) must PASS;
#    ArcRift and Ollama are OPTIONAL and surface only as WARN.
python3 scripts/doctor.py
```

- `bootstrap.py` is safe to re-run — every step is idempotent. Run it again any time
  `projects/` goes missing or the agent shims look stale.
- `doctor.py` exits `0` when every required check passes. Use `--json` for a
  machine-readable table.

Then open a session at the repo root:

```bash
claude
```

Everything from here on happens **inside that session** by invoking the three
orchestration skills.

---

## 3. Driving the org end to end

You operate DasLab through three skills, invoked in the `claude` session. Nothing
runs on a timer; each invocation is one explicit operator action.

| You want | Command |
|---|---|
| Decompose a goal / start a new project | `/daslab-plan "<goal>"` |
| Run ONE work wave (every actionable ticket) | `/daslab-cycle` |
| Run a smaller, bounded wave of at most N tickets | `/daslab-cycle 10` |
| Drain the Founder-approved goal queue across waves | `/daslab-run` |

The normal end-to-end path:

```text
claude
> /daslab-plan "Build a CLI that converts CSV to JSON, with tests and a README"
   # → for a new project, runs the Founder Discovery Gate first (see §4),
   #   then writes stage-gated epics + PR-sized tickets to the target board.

> /daslab-cycle
   # → runs one wave: triage → select → dispatch in parallel → collect → report.

> /daslab-run
   # → supervises: plan the next approved goal when the board empties, then run
   #   cycle waves until the tickets drain or a real stop condition appears.
```

### `/daslab-plan "<goal>"` — goal to tickets (dispatches nothing)

Plays the CEO/CPO decomposition role. It first decides which board the goal targets
(QONUN Project Placement Law, §4): a **project** goal's tickets go to that project's
own board, `projects/<slug>/board-tickets/`, carrying `project: <slug>`; a
**platform** (org-engine) goal's tickets go to `board/tickets/` and carry no
`project:` field. It then produces the hierarchy `Goal → Epic → Ticket` — epics get
`status: backlog` and a lead/manager owner per RACI; child tickets are PR-sized with
concrete acceptance criteria, `status: todo`, and an IC assignee. For an **AI-agent
goal** the AADL law applies: exactly one epic per lifecycle stage, each epic's
acceptance criteria being that stage's GATE checklist. `/daslab-plan` files tickets;
it never dispatches work. Full spec:
[`/daslab-plan`](../.claude/skills/daslab-plan/SKILL.md).

### `/daslab-cycle [N]` — one wave

Runs exactly one operator-invoked wave over the org `board/tickets/` (platform work).
A project's own board is run by a `/daslab-cycle` wave invoked in that project's
context — it is never pulled into the org wave. The wave:

1. **Prewarm.** One `recall_context` call (if ArcRift is wired) before any subagent.
2. **Triage** (orchestrator-only edits): reap stale worktrees; route unassigned
   `todo` tickets per RACI; reroute any `in_review` where assignee == author to the
   author's reviewer; skip external blockers.
3. **Select** every actionable ticket, priority order `p0 → in_review →
   in_progress → todo`. Tickets behind an open AADL gate, an unmet `depends_on:`, or
   an unresolved `[NEEDS CLARIFICATION: …]` marker are skipped and counted.
4. **Dispatch** all selected tickets **in parallel**, one git worktree per
   code-touching ticket (`.claude/worktrees/<TICKET-ID>/`), each subagent spawned
   with an **explicit** model.
5. **Collect & verify**: re-read each ticket, confirm the file actually changed,
   gate engineering `done` on green CI, reap resolved worktrees.
6. **Report** the wave (see §5).

There is **no policy cap** on wave size. Real concurrency is bounded only by the
Claude Code harness, the AADL gate order, and the same-repo-zone correctness guard
(one ticket per repo zone per wave). The optional `N` is a deliberate smaller-wave
bound for a quick test run. Full spec:
[`/daslab-cycle`](../.claude/skills/daslab-cycle/SKILL.md).

### `/daslab-run` — drain the approved queue

The operator-invoked **supervisor**. It is work-aware: when a wave moves at least one
ticket it starts the next wave immediately; when a wave produces zero changes it
treats the board as drained and stops with a report. When the board empties it plans
the next `founder_approved` queue item (per the `/daslab-plan` rules) and keeps
cycling. It is **not** a daemon or a night loop — when the session ends, the run
ends, and you can interrupt it at any time. If two consecutive waves produce no state
change, it stops with a blocker report rather than spinning. Full spec:
[`/daslab-run`](../.claude/skills/daslab-run/SKILL.md).

---

## 4. Planning a NEW project — the Founder-Approved Goal Queue

A new project does **not** become board tickets the moment you describe it. It first
passes a discovery gate so the org never invents work for itself. When `/daslab-plan`
sees a goal whose `projects/<slug>/APPROVED-GOAL-QUEUE.md` does not yet exist, it
stops normal decomposition and runs intake:

1. **Discovery — at least 10 questions.** The planner asks the Founder ten or more
   concise discovery questions before drafting anything: target user, core problem,
   must-have outcome, non-goals, business model, success metrics, deadline, budget,
   existing assets, brand, integrations, compliance/legal constraints,
   deployment/domain, support expectations, and risk tolerance. In a non-interactive
   run it outputs the questions and stops — it never guesses.

2. **Research.** After the answers, it does current global research with cited
   sources: market and competitor scan, user expectations, technical options,
   regulatory/compliance considerations, channel/SEO signals when relevant,
   pricing/unit economics when relevant, and key risks.

3. **Queue file — project folder only.** It creates the project folder first, then
   writes the research and the queue **only inside it**, honoring the Project
   Placement Law:

   ```text
   projects/<slug>/
     APPROVED-GOAL-QUEUE.md          # founder answers, research snapshot, sources,
                                     # assumptions, non-goals, prioritized queue table
     docs/01-planning/               # supporting planning notes
   ```

   The queue table carries `order`, `goal_slug`, `outcome`, `why_now`,
   `research_basis`, `owner`, `status`, and `ticket_refs`. Status values:
   `candidate → founder_approved → planned → active → done` (plus `blocked`,
   `rejected`).

4. **Explicit Founder approval.** No board tickets are created until the Founder
   explicitly approves — a clear signal such as `APPROVED:` or `TASDIQLANDI:`. Only
   then does `/daslab-plan` decompose the next `founder_approved` item, flip it to
   `planned`, and add the ticket refs. `/daslab-cycle` and `/daslab-run` plan only
   from this approved queue; they never fabricate a goal to keep agents busy.

A worked example of the full flow is in [EXAMPLE-RUN.md](EXAMPLE-RUN.md).

---

## 5. Reading a wave's output

After `/daslab-cycle` returns, the report is what you read. It contains:

- **A dispatch table** — `ticket → old status → new status → agent → one-line
  outcome` for every ticket the wave touched.
- **Blocked tickets** with their precise reasons; escalations; and any orphaned
  `todo` tickets that could not be routed.
- **Skipped counts** — tickets held back as `gate-blocked` (an open AADL gate),
  `dep-blocked` (an unmet `depends_on:`), or `clarify-blocked` (an unresolved
  `[NEEDS CLARIFICATION: …]` marker).
- **What the next wave would pick up.**

The ground truth always lives in the files, so you can verify the report directly:

```bash
# Current status of every platform ticket
grep -h -E '^(id|status|assignee):' board/tickets/DAS-*.md

# Just the tickets still open
grep -rl 'status: in_progress' board/tickets/

# What a specific ticket did and why — its append-only audit log
sed -n '/## Log/,$p' board/tickets/DAS-1001-*.md

# Any open worktrees the orchestrator created this wave
git worktree list
```

The orchestrator also writes a KPI trail to `board/.wave-log` (gitignored). It is
read by the wave-KPI tooling and the passive cockpit:

```bash
python3 scripts/wave_kpi.py     # per-wave throughput from board/.wave-log
python3 scripts/cockpit.py      # passive operator cockpit (read-only)
```

A ticket is only `done` when its work is real: for an engineering ticket that means a
merged PR with green CI — the orchestrator confirms it (`gh pr checks <PR>`) rather
than trusting a subagent's report. If CI is red or still running, the ticket goes
back to `in_progress` for the next wave.

---

## 6. The board lifecycle a ticket moves through

One markdown file in `board/tickets/` = one ticket (a project's tickets live in its
own `projects/<slug>/board-tickets/`). Filename `DAS-<n>-<slug>.md`, ids strictly
increasing (next = max existing + 1; an empty board starts at DAS-1001). Frontmatter
is snake_case YAML; the full schema and routing rules are in
[`../board/README.md`](../board/README.md) and [`../board/ROUTING.md`](../board/ROUTING.md).

**Status enum — the only valid values, in flow order:**

```text
backlog → todo → in_progress → blocked → in_review → done
```

A ticket's typical journey across waves:

1. **`backlog`** — an epic, or a not-yet-ready item. Created by `/daslab-plan`.
2. **`todo`** — ready to work. If `assignee` is empty, the next wave's triage routes
   it to a role per [RACI](../governance/policies/raci.md) and logs the routing.
3. **`in_progress`** — a wave dispatched it; a subagent is working it in its own
   worktree (WIP = 1, one ticket per role per subagent).
4. **`blocked`** — work cannot proceed; the `## Log` records a precise reason.
   External-dependency blocks (RAHMAT, UZINFOCOM, IKPU, tax, legal entity) are
   tracked and never auto-dispatched.
5. **`in_review`** — built and handed to the reviewer. `assignee` switches to the
   author's manager per `ROUTING.md`; an agent never reviews its own work.
6. **`done`** — accepted. For engineering, that means a merged PR with green CI.

**Rules that matter to you as operator:**

- **Append-only log.** Every state change appends a `## Log` entry (who, what, why) —
  never a silent edit. The log is your audit trail.
- **No orphans.** Every non-epic ticket carries `parent:` and `goal:`.
- **Platform vs. project.** A `board/tickets/` ticket must not carry a `project:`
  field — `scripts/board_lint.py` fails any that does. Project tickets carry
  `project: <slug>` and live on the project's own board.

You rarely edit a ticket by hand: the orchestrator and the role subagents mutate the
files for you. Read them, or just ask the session in plain language.

---

## 7. The QONUN laws in practice (what each means for a day of work)

QONUN ("law") rules are hard, binding constraints defined in
[`../CLAUDE.md`](../CLAUDE.md) and [`../AGENTS.md`](../AGENTS.md). Day to day, they
shape what you can and cannot do:

1. **Project Placement.** Everything for a project — code, docs, planning, queue, and
   tickets — lives ONLY under `projects/<name>/` (gitignored; each project manages
   its own git). One project = one folder, so deleting it is a single
   `rm -rf projects/<name>`. In practice: never expect a project's files in `docs/`,
   `scripts/`, the department trees, or the org board. If `/daslab-plan` files a
   project goal, look for its tickets under `projects/<slug>/board-tickets/`, not
   `board/tickets/`.

2. **AI-Agent Lifecycle (AADL).** Every AI-agent build moves through six ordered,
   gated stages — Planning → Design → Development → Testing → Deployment →
   Maintenance (GATE-1…GATE-6). In practice: `/daslab-plan` emits exactly one epic
   per stage, and `/daslab-cycle` will not dispatch a ticket sitting behind an open
   gate — you will see it counted as `gate-blocked` in the report. Shipping to
   production with GATE-5 open is forbidden. Binding source:
   [`../governance/policies/ai-agent-lifecycle.md`](../governance/policies/ai-agent-lifecycle.md);
   order enforced by `scripts/check_gates.py`.

3. **Model Allocation.** Each agent runs on the Claude model its task complexity
   needs — opus ×10 (the eight gate owners plus the CTO and Security Lead), sonnet
   ×19, haiku ×3. In practice: the model is **always** passed explicitly on dispatch
   (the frontmatter alone is not trusted), and an agent never upgrades its own model —
   hard work escalates up the reporting line. If you change the table, re-run
   `python3 scripts/gen_subagents.py`. Canon:
   [`../governance/policies/model-allocation.md`](../governance/policies/model-allocation.md).

4. **Persistent Memory (ArcRift).** Each unit of work recalls context at the start
   and stores a decision at the end, scoped strictly by a flat project key (`daslab`,
   or `daslab-<slug>`). In practice: mixing one project's facts into another is
   forbidden, and stale facts are pruned, not kept. This layer is **optional** for
   booting — see §8.

A fifth binding rule, the **Founder-Approved Goal Queue** (§4), governs how new work
enters the org: ten-plus discovery questions, research, a project-folder queue file,
and explicit Founder approval before any ticket exists.

---

## 8. Where ArcRift fits (optional)

DasLab's long-term memory lives in **ArcRift**, a local MCP server wired in
[`../.mcp.json`](../.mcp.json). It lets work survive across sessions:

- A wave calls `recall_context` once at the start (prewarm) and each unit of work
  enqueues a `store_memory` payload at the end; the orchestrator drains the outbox
  after the wave. Memory is scoped strictly by the flat project key.
- Graph triple extraction routes to a local Claude bridge; embeddings use a local
  Ollama model. The memory policy is
  [`../governance/policies/memory-modes.md`](../governance/policies/memory-modes.md);
  the binding rule is the Persistent Memory Law in [`../CLAUDE.md`](../CLAUDE.md).

ArcRift and Ollama are **not required to boot**. `scripts/doctor.py` treats them as
`WARN`, not `FAIL`, so you can run the entire org without them — recall and store
simply become best-effort no-ops, and every other guarantee (the board, the waves,
the gates, the release gate) is unaffected.

---

## 9. Quality gate before you ship

The release gate is `scripts/diagnostics.py`: a weighted, all-or-nothing 7-dimension
scorer (Documentation 20, Architecture 20, Code quality 15, Consistency 15,
Portability 15, Security 10, Git hygiene 5 = 100). It exits non-zero unless the score
is exactly **100/100**.

```bash
python3 scripts/diagnostics.py        # prints SCORE = 100/100 on a clean tree

# Full local gate before opening a PR:
ruff check scripts && python3 -m pytest -q && python3 scripts/diagnostics.py
```

CI ([`../.github/workflows/ci.yml`](../.github/workflows/ci.yml)) runs the same gate
plus a long validator chain (`board_lint.py`, `check_gates.py`, `check_links.py`,
`check_project_isolation.py`, and more) on every PR and push to `main`. The core
contribution rule is **one issue = one branch = one PR = one worktree**; nothing
merges to `main` without an approving review and green CI, and you may not review your
own PR. See [`../CONTRIBUTING.md`](../CONTRIBUTING.md).

---

## 10. Where to go next

| For | Read |
|---|---|
| The canonical runtime description | [06-CLAUDE-CODE-MODE.md](06-CLAUDE-CODE-MODE.md) |
| The human operator runbook | [04-OPERATIONS.md](04-OPERATIONS.md) |
| The fuller operator manual (board model, approvals, troubleshooting) | [USER-GUIDE.md](USER-GUIDE.md) |
| Org chart, the 32-agent roster, reporting lines | [02-ORG.md](02-ORG.md) · [AGENT-ROSTER.md](AGENT-ROSTER.md) |
| A worked end-to-end example | [EXAMPLE-RUN.md](EXAMPLE-RUN.md) |
| The full script inventory and run order | [05-SCRIPTS.md](05-SCRIPTS.md) |
| The company charter and binding policies | [`../governance/charter.md`](../governance/charter.md) · [`../governance/policies/`](../governance/policies/) |
| Feature flags (latent machinery, default off) | [`../config/features.yaml`](../config/features.yaml) |

*Invoke a wave and the org goes to work.*
