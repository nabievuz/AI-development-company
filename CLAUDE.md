# DasLab — Claude Code Project Instructions

> Org spec: [`AGENTS.md`](AGENTS.md). Docs: [`docs/README.md`](docs/README.md).

## QONUN — Project Placement Law

**Every new project lives ONLY inside `projects/<project-name>/`.**

- When a project is assigned, the first step is to create a folder named after
  it inside `projects/`. EVERYTHING belonging to the project (code, docs,
  scripts, design, tests, cache) stays inside that folder and never leaks out.
- **Tickets too — project tickets live in the project, platform tickets in the
  org board.** A project's board tickets live ONLY in the project's own board,
  `projects/<project-name>/board-tickets/` (each project keeps its tickets on its
  own board), never in the org `board/tickets/`. The org `board/tickets/` is reserved
  EXCLUSIVELY for **DasLab-platform (org-engine) tickets** — work on the engine,
  governance, policies, skills, and validators themselves. A project ticket
  never carries into `board/tickets/`; an org-engine ticket never carries into a
  project board. `scripts/board_lint.py` fails any `board/tickets/` ticket that
  declares a `project:` field.
- Placing project-specific files in `docs/`, `scripts/`, the department trees
  (`engineering/`, `product/`, …), or external repos is FORBIDDEN. Department
  docs may mention a project by name only — they never host its content.
- Why: project material used to scatter across the whole repo (60+ files),
  turning a project deletion into a large cleanup operation.
  One project = one folder → deleting it is a single `rm -rf projects/<name>`.
- `projects/` is gitignored — each project manages its own git repo.

## QONUN — AI Agent Lifecycle (mandatory standard)

**Every AI-agent program is built on the six-stage lifecycle:**
`Planning → Design → Development → Testing → Deployment → Maintenance`.

- Source (binding policy): [`governance/policies/ai-agent-lifecycle.md`](governance/policies/ai-agent-lifecycle.md).
- Each stage is closed by its GATE checklist and logged in the project's
  `README.md` stage-board. Skipping a stage is FORBIDDEN.
- A new AI-agent project bootstraps from the skeleton in policy §2
  (`docs/01-planning/` … `docs/06-maintenance/`).
- `/daslab-plan` decomposes AI-agent goals into stage-gated epics;
  `/daslab-cycle` does not dispatch tickets that sit behind an open gate.
- Shipping to production with GATE-5 open is FORBIDDEN.

## QONUN — Founder-Approved Goal Queue

**A new project passes a Founder discovery gate before it becomes board
tickets.**

- When `/daslab-plan` sees a new project or an unclear product goal, it does NOT
  create tickets immediately. It first asks the Founder at least 10 questions and
  gets the answers, or the Founder explicitly declines/waives them.
- After the answers, current global research is done: a sourced conclusion
  covering market, competitors, regulatory/compliance, technical architecture,
  pricing/unit economics, SEO/channel, and risks.
- The result is stored only in the project folder:
  `projects/<project-name>/APPROVED-GOAL-QUEUE.md` (+ the needed planning docs).
  The Project Placement Law is not broken.
- Until the Founder explicitly approves the queue (an explicit signal such as
  `APPROVED:` or `TASDIQLANDI:`), no board tickets are created.
- `/daslab-cycle` (or a future supervisor) plans only the next goal from that
  approved queue; agents never invent new goals just to stay busy.

## QONUN — Model Allocation Law

**Each agent runs on the Claude model its task complexity needs** — the task
decides, not the title. Canonical table:
[`governance/policies/model-allocation.md`](governance/policies/model-allocation.md)
— opus ×10 (8 gate owners + cto/security-lead permanently on opus),
sonnet ×19 (the execution core), haiku ×3 (high-frequency templated work).
Fable 5 is disabled/retired — Tier F is decommissioned, with no path back.

- On dispatch, `model` is ALWAYS passed explicitly — the frontmatter alone is
  not trusted (claude-code#44385).
- There is NO parallel cap and NO opus wave-mix cap (the owner removed both on
  2026-06-14 — the Max limit barely moved, and both were a free brake).
  A wave = all actionable tickets; only the harness limits real parallelism.
  The one remaining constraint is the CORRECTNESS rule: no two tickets target
  the same repo zone in one wave (merge conflicts + rework lower throughput),
  plus the AADL gate order.
- Session recommendation: `/daslab-cycle` → sonnet, `/daslab-plan` → opus, heavy
  architecture/debug sessions → opus (permanent — Tier F is decommissioned).
- An agent never upgrades its own model: hard work → escalate (ROUTING.md).
- If the table changes: re-run `python3 scripts/gen_subagents.py`.

## QONUN — Persistent Memory Law (ArcRift)

**DasLab's long-term memory lives in ArcRift.** Context is not lost between
sessions — each agent starts work by recalling from ArcRift and finishes by
writing back to ArcRift.

- Source: a local ArcRift (the MCP server is wired in `.mcp.json` under the name
  `ArcRift`; backend `~/ArcRift`, local SQLite). LLM modules:
  - **Graph extraction (triples) → Claude subscription.** `~/ArcRift/claude-bridge`
    (`claude -p`, sonnet) runs as a local OpenAI-compatible endpoint (`:8787`);
    ArcRift `.env`: `GRAPH_BACKEND=local-openai`. The bridge auto-starts via
    launchd (`dev.arcrift.claude-bridge`).
  - **Embeddings → local Ollama `nomic-embed-text`.** Anthropic has NO embeddings
    API, so this layer is not tied to Claude — Ollama is mandatory.
- **At the start of work (MANDATORY):** call `recall_context` — the current
  ticket/task text as `prompt`, `project` = `daslab` (or `daslab-<project>` if
  project-specific). Read the returned `<ARCRIFT_retrieved_context>` block before
  touching anything.
- **At the end of work (MANDATORY):** call `store_memory` — briefly record the
  decision, the reason, the result, and the next step (`project` = same as
  above). Write only a non-duplicate fact useful to a future session; do not
  write what the repo already stores (code, git history).
- Project scoping is STRICT: mixing one project's facts into another is FORBIDDEN
  (the `project` name enforces project isolation). For a global search use
  `search_memory`; for a project summary use `get_project_summary`.
- Delete a stale/incorrect fact with `prune_memory` — keeping a wrong memory is
  FORBIDDEN.
- If the MCP server needs rebuilding: `cd ~/ArcRift/backend && npx esbuild
  src/mcp/server.ts --bundle --platform=node --packages=external
  --outfile=dist/mcp/server.js`.
