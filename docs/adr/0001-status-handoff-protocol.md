# ADR 0001 — Completion status protocol + finding format (fleet-wide)

**Status:** Accepted
**Date:** 2026-06-06
**Scope:** Platform / agent capability
**Relates:** the status/finding protocol used fleet-wide by every role overlay and the `/daslab-cycle` handoff; later refined by ADR-0005 (worktree-per-ticket dispatch) and ADR-0010 (DGO-X control plane).

## Context

Running the fleet autonomously surfaced two recurring stalls:

1. **`in_review` self-review deadlock** — an author moves their own work to `in_review`
   and then nothing happens, because `in_review` is a reviewer's queue, not a parking
   spot. No distinct reviewer is assigned, so the ticket sits forever.
2. **Orphaned follow-ups** — an agent finishes work but notes unresolved concerns only in
   a free-text comment. The concern has no owner and no ticket, so it silently drops.

The root cause is the same: **a unit of work could end without a machine-readable terminal
signal.** The orchestrator could not reliably tell *done* from *stuck*.

The fix lives at the skill layer: every skill ends in exactly one of
`DONE` / `DONE_WITH_CONCERNS` / `BLOCKED` / `NEEDS_CONTEXT`, and review output uses a
fixed `[SEVERITY] (confidence: N/10) file:line — summary` finding shape. These are the
two cheapest, highest-leverage primitives — they add no runtime dependency.

## Decision

**Adopt a mandatory completion status protocol and a standard finding format, encoded in
the binding `/daslab-cycle` orchestration skill.**

- Every agent ends each unit of work with a final
  `STATUS: <ONE_OF_FOUR> — <≤12-word reason>` line:
  - `DONE` → move to `done` with evidence.
  - `DONE_WITH_CONCERNS` → move to `done` **and** open a follow-up issue **with a named
    owner**. A concern in a comment only is invalid.
  - `BLOCKED` → move to `blocked`, one-line blocker, `@`-mention the unblocker.
  - `NEEDS_CONTEXT` → return to requester with one specific question; never sit in `in_review`.
- **`in_review` is a reviewer's queue, never the author's parking spot** — authors may not
  leave their own work there.
- Review/audit output (the `review` / `security-audit` skills) emits
  `[SEVERITY] (confidence: N/10) path:line — summary`, `SEVERITY ∈ {CRITICAL, P1, INFORMATIONAL}`.

Three matching anti-patterns were added to the `/daslab-cycle` anti-pattern list.

## Consequences

**Positive:** the orchestrator gets an unambiguous per-unit signal; the two known
stalls become structurally impossible (an author can't silently park in `in_review`, and a
concern can't exist without an owned ticket); review output is parseable.

**Negative / accepted:** prompt-layer only — it relies on agents following the skill, not
on a hard runtime gate. A future enhancement could have the orchestrator *enforce* a
terminal `STATUS:` line (reject a wave exit without one). Deferred until we see
adherence in practice.

## Revisit triggers

- If agents still exit without a `STATUS:` line → add cycle-level enforcement in
  `.claude/skills/daslab-cycle/SKILL.md` or a validator hook that rejects missing
  terminal status before the wave report is accepted.
- When the `review`/`security-audit` skills change → confirm their output matches the
  finding format and tighten if drift appears.
