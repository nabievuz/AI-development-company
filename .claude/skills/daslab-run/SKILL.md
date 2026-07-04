---
name: daslab-run
description: >
  Drain DasLab work from the Founder-approved goal queue: plan the next approved
  queue item when the board is empty, then run /daslab-cycle waves until the
  tickets drain or a real stop condition appears. Use when the operator asks to
  run the org end-to-end, continue until tickets are done, or process the
  approved goal queue. This is an operator-invoked supervisor, not a background
  timer or night script.
---

# DasLab run — approved queue supervisor

You are the DasLab supervisor for one operator-invoked run. You coordinate
`/daslab-plan` and `/daslab-cycle` behavior inside the current session.

## Cadence (W2 — work-aware, no fixed sleep)

This supervisor is **work-aware**: it advances immediately while progress is
being made and stops cleanly when the board is drained. There is no fixed sleep,
no polling interval, and no night-loop timer. The retired 30-minute sleep cycle
is gone; every pause must have a concrete reason.

**Advance rule:** if the wave that just finished moved at least one ticket
(status change, queue item planned, or new tickets created), start the next
`/daslab-cycle` wave immediately — no delay, no sleep.

**Stop rule:** if a wave produces zero ticket/queue/status changes, treat the
board as effectively drained for this run. Do not start another wave. Report the
stop condition (see Section "Guardrails" below).

**Kill-switch path (LAW 10 — bounded, operator-interruptible):** because this
supervisor runs inside the operator's Claude Code session, the operator can
interrupt at any point: closing the session, pressing Ctrl-C, or issuing a new
command all terminate the run cleanly. There is no daemon, no background process,
and no persistent timer that outlives the session. If you detect that the last
two consecutive waves produced no state change (no ticket moved, no queue item
changed), stop immediately and emit a blocker report — do not continue looping.
This is the software kill-switch that prevents runaway cycling when the board is
genuinely stuck.

## Operating loop

1. Confirm repo identity: `board/tickets/` exists.
2. Read `board/README.md`, `board/ROUTING.md`, `.claude/skills/daslab-plan/SKILL.md`,
   `.claude/skills/daslab-cycle/SKILL.md`, and any
   `projects/*/APPROVED-GOAL-QUEUE.md`.
3. If actionable tickets exist, run one `/daslab-cycle` wave.
4. Re-read board state. If the wave did work (any ticket or queue change), go to
   step 3 immediately. If the wave did no work, proceed to step 5.

   Between waves, append an idle marker to `board/.wave-log` (create if absent;
   never truncate):
   `[idle <N>s before next wave — <HH:MM:SS>]` where N is the actual elapsed
   seconds since the previous wave ended and HH:MM:SS is the current UTC time.
   This is consumed by `scripts/wave_kpi.py` — do not alter the format.

5. When the board is drained or the wave produced no progress:
   - If non-done tickets are blocked on external input, open lifecycle gates,
     CI/security, or Founder approval, report and stop.
   - If exactly one next `founder_approved` queue item exists, apply the
     `/daslab-plan` rules to create tickets **on the target board per the
     Placement Law** (a project item → that project's own
     `projects/<slug>/board-tickets/`, carrying `project: <slug>`; a platform
     item → org `board/tickets/` with no `project:` field), mark that queue item
     `planned`, then continue cycling (return to step 3). This supervisor cycles
     the org `board/tickets/` (DasLab-platform work); a project's tickets are run
     by a `/daslab-cycle` wave in that project's own context.
   - If no approved queue item exists, report "approved queue drained" and stop.
   - If a new project has no approved queue, run the `/daslab-plan` Founder
     Discovery Gate: ask at least 10 questions, require global research, draft
     the queue, and stop for explicit Founder approval.

## Guardrails

- **No fixed sleep or timer.** Cadence is driven entirely by whether the prior
  wave did work. Never insert `sleep`, a fixed wait, or a polling interval.
- **Bounded (LAW 10).** If two consecutive waves both produce zero state change,
  stop with a blocker report. Do not loop indefinitely on a stuck board.
- Never invent goals. The only feedstock is an explicit Founder request or a
  `founder_approved` queue item.
- Never bypass AADL gates, same-repo-area correctness guards, external blockers,
  security reviews, CI-green requirements, or git worktree law.
- This is not a daemon. When the current session ends, the run ends.

## Report

End with:
- waves run
- queue items planned
- tickets completed / left
- blockers
- next Founder decision needed, if any
