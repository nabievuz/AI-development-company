# 04 — Operations (Human Runbook)

> How a human operator runs DasLab. DasLab runs as Claude Code subagent sessions
> over a file-based board — see [06-CLAUDE-CODE-MODE.md](06-CLAUDE-CODE-MODE.md)
> for the full runtime reference.

## Operating the org

Open Claude Code at the repo root and invoke work directly — there is no HTTP
API, no timer, and no autonomous background driver:

```bash
cd ${HOME}/projects/daslab
claude
# /daslab-plan "<goal>"     # decompose a goal into board tickets
# /daslab-cycle             # run ONE wave: dispatch actionable role subagents
# /daslab-run               # drain the Founder-approved goal queue end-to-end
```

- **Plan** with `/daslab-plan "<goal>"` to break a goal into PR-sized tickets with
  owners per RACI. A project goal's tickets are written to the project's own board
  (`projects/<slug>/board-tickets/DAS-*.md`); `board/tickets/DAS-*.md` holds only
  DasLab-platform (org-engine) tickets (QONUN — Project Placement Law).
- **Run a wave** with `/daslab-cycle` — it triages the board and dispatches every
  actionable role subagent in parallel. There is no policy parallel cap;
  correctness is bounded by AADL gate order, same-repo-area guards, and git
  worktree isolation.
- **Drain the queue** with `/daslab-run` to plan the next Founder-approved goal
  when the board is empty, then run cycle waves until the tickets drain.
- **Stop / pause:** there is no timer, driver, or night-loop process to stop.
  Stop the active Claude Code session if you do not want to launch another wave.
- **Monitor:** tickets are files under `board/tickets/`; read them directly (e.g.
  `grep -l 'status: open' board/tickets/DAS-*.md`). There is no live dashboard
  endpoint.
- **Seed / re-seed work:** there is no active product currently. See
  [05-SCRIPTS.md](05-SCRIPTS.md) for the script inventory.

For role definitions, model tiers, and the full wave protocol, see
[06-CLAUDE-CODE-MODE.md](06-CLAUDE-CODE-MODE.md).
