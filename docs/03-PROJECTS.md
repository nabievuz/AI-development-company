# 03 — Projects

> What DasLab builds. There is currently **no active product** — every past
> project is retired, and their dedicated workspaces have been purged from the repo.

## Retired projects (all `cancelled`)

| Project | Old codebase | Note |
|---|---|---|
| Q2 2026 Operating Cadence | `governance/` | bootstrap-era org-setup project |
| Platform Foundations | `engineering/` | bootstrap-era |
| Roadmap Cycle 1 | `product/` | bootstrap-era |
| Design System v0 | `design/` | bootstrap-era |
| Launch Marketing Engine | `marketing/` | bootstrap-era |
| Ops Foundations | `operations/` | bootstrap-era |

Several retired product attempts (DM-agent / SaaS experiments) also existed;
their codebases and docs have been removed from the repo entirely.

## Adding a new project

DasLab starts a new project through `/daslab-plan`, but planning is gated:

1. The planner creates or identifies `projects/<project-slug>/` first.
2. The planner asks the Founder at least 10 discovery questions before any board
   ticket exists.
3. The planner enriches the answers with current global research: market,
   competitors, users, regulatory/compliance, technical options, pricing/unit
   economics, SEO/channels where relevant, and risks. Research must include
   source links.
4. The planner writes `projects/<project-slug>/APPROVED-GOAL-QUEUE.md` and
   supporting notes under `projects/<project-slug>/docs/01-planning/`.
5. The Founder explicitly approves the queue (`APPROVED:` / `TASDIQLANDI:`).
6. Only then may `/daslab-plan` decompose approved queue items into tickets —
   written to the **project's own board**, `projects/<project-slug>/board-tickets/`
   (each project keeps its tickets on its own board), never into the org
   `board/tickets/`.
   The org `board/tickets/` is reserved for DasLab-platform (org-engine) tickets
   only (QONUN — Project Placement Law).

The approved goal queue is the source of truth for autonomous refill. When the
board drains, `/daslab-cycle` or `/daslab-run` may plan the next
`founder_approved` queue item — its tickets land on that project's own board and
are run by a wave in the project's own context, while the org `board/tickets/`
carries only platform work. It may not invent new work.

Minimal queue shape:

```markdown
# Approved Goal Queue — <project>

Founder approval: pending | approved
Research snapshot: YYYY-MM-DD

| Order | Goal slug | Outcome | Why now | Research basis | Owner | Status | Ticket refs |
|---|---|---|---|---|---|---|---|
| 1 | mvp-foundation | ... | ... | sources/notes | cpo | founder_approved | — |
```

Status values: `candidate`, `founder_approved`, `planned`, `active`, `done`,
`blocked`, `rejected`.
