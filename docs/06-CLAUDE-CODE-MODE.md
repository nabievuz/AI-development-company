# 06 — Claude Code Mode

> **How the DasLab runtime works.** DasLab runs as a single Claude Code session at
> the repo root that orchestrates the 32-role org as subagents over a file-based
> board. There is no server, no HTTP API, and no background timer — work advances
> when the operator invokes a wave.

## How it works

DasLab is a Claude Code session driving 32 role subagents against a file-based
board:

- **Board.** Work items are markdown files under `board/tickets/*.md`
  ([schema](../board/README.md)) — plain files, no database.
- **Roles.** Each role is a generated subagent definition in
  `.claude/agents/<role>.md`, produced by `scripts/gen_subagents.py` from the
  per-role overlays (`<dept>/agents/<role>/AGENTS.md`) plus the model-allocation
  table.
- **Waves.** `/daslab-cycle` runs one wave: it triages the board, dispatches every
  actionable role subagent in parallel, collects their results, and reports.
  Concurrency is bounded by the Claude Code harness, AADL gate order, and the
  same-repo-area correctness guard (one ticket per repo zone per wave) — not by a
  timer or a policy cap.
- **Planning.** `/daslab-plan "<goal>"` decomposes a goal into board tickets
  (goal → epic → ticket) with owners per RACI.
- **Approvals.** Board approvals (hires, budget, strategy) and production go-live
  stay with the human operator in the main session — never auto-approved.
- **Review routing.** When a ticket reaches `in_review`, the cycle reroutes it to
  the author's manager per `board/ROUTING.md` — an agent never reviews its own
  work.
- **Git.** One issue = one branch = one PR, each agent isolated in its own git
  worktree off fresh `origin/main`; nothing merges to `main` without green CI.

The org tree (`<dept>/CLAUDE.md` charters, `<dept>/agents/<role>/AGENTS.md`
overlays), the precedence chain (AGENTS.md §2), and the Kanban status flow govern
how every role behaves.

## How to run

```bash
cd ${HOME}/projects/daslab && claude
```

Then, inside the session:

| You want | Type |
|---|---|
| Start a new project | `/daslab-plan "<goal>"` (asks Founder questions, researches, drafts approved queue) |
| Turn an approved queue item into tickets | `/daslab-plan "<approved goal slug>"` |
| Run every actionable ticket | `/daslab-cycle` |
| Drain approved queue until a blocker/approval is needed | `/daslab-run` |
| Run a smaller bounded wave | `/daslab-cycle 10` |
| Inspect the board | read `board/tickets/`, or just ask |

Work advances when the operator invokes a wave; that wave may dispatch every
actionable ticket, bounded only by the Claude Code harness, AADL gate order, and
same-repo-area correctness guards. There is no night driver or background loop.

## Maintenance

- Edited a role overlay or added/removed a role (`<dept>/agents/<key>/`)?
  Regenerate the shims:
  ```bash
  python3 scripts/gen_subagents.py
  ```
  This rewrites `.claude/agents/*.md` and `board/ROUTING.md`. Never edit those by
  hand — the overlays remain the single source of truth.
- Only living, runnable tooling lives in `scripts/`; see
  [05-SCRIPTS.md](05-SCRIPTS.md) for the inventory.
