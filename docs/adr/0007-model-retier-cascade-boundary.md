# ADR 0007 — Model re-tier boundary: what may drop to haiku, what stays opus

- **Status:** Proposed (authored by Backend EM; **CTO ratifies — GATE-2 / RACI 3.1 A**)
- **Date:** 2026-06-19
- **Scope:** Platform / model allocation
- **Deciders:** Backend EM (author/MGR), **CTO (accountable)**; Security Lead (consulted — opus stays on security-touching work)
- **Relates:** DAS-1366 (implementation — concrete table edit + `gen_subagents.py` rerun);
  `governance/policies/model-allocation.md`; ADR 0005/0006/0008/0009

## Context

The documented baseline mix was **55% opus / 0% haiku**, and a wave finishes only when its
**slowest** agent finishes — so the fleet ran at **opus latency for mechanical work too**.
The goal is **≥ 25% haiku share** of dispatch by re-tiering mechanical, templated,
high-frequency work to the cheap/fast tier, while gate/architecture/security work stays
opus (LAW 3).

This ADR records the **boundary** (which work is re-tier-eligible and which is permanently
opus) as a design decision, because crossing it wrong is a *quality* failure (T7), not a
cost tweak. The concrete policy-table change and the mandatory `gen_subagents.py` rerun are
the implementation, owned by DAS-1366 — this ADR is the rule that change must obey.

> **Note on scope boundary.** This ADR covers a **static, data-driven re-tier of roles/
> subtask classes** in `model-allocation.md`. The *dynamic per-task cascade* (haiku drafts
> → sonnet/opus verify at runtime) is out of scope here. This ADR sets the boundary both
> will respect.

## Decision

**Re-tier by task complexity, never by title (LAW 3), within a fixed opus floor.**

1. **Eligible to drop to haiku** — mechanical, templated, deterministic-output, high-
   frequency work where a wrong output is cheaply caught by a downstream gate: status/board
   bookkeeping, routine doc/templated-copy generation, SEO metadata, support-templating
   (the two roles already on haiku), and clearly mechanical *subtasks* of larger tickets.
2. **Permanent opus floor (never re-tiered, LAW 3 + GATE model):**
   - **Every AADL GATE decision** (the gate owner role acting as gate signer).
   - **Architecture / ADR authorship and ratification** (this very class of work).
   - **The security sign-off gate stays opus** — `security-lead` is permanently
     opus and is the opus control on all security-touching work: a cheaper tier
     never *reviews* a security/red-team item. The IC executor `security-eng`
     runs red-team/scans on **sonnet** per the operator-committed baseline
     (`model-allocation.md`); the opus guarantee is the Security Lead review gate,
     not the IC tier (CTO ruling, 2026-06-19). `cto` and
     `security-lead` are permanently opus per `model-allocation.md` and that does
     not move.
   - **Dispute resolution / high-risk planning.**
3. **Re-tier is data-driven, not a guess.** A role/subtask moves tiers based on what it
   *actually does* (measured via routing-mix data once available), recorded in
   DAS-1366. Absent data, the conservative default is **no down-tier** — we do not
   speculatively cheapen a role and hope.
4. **The generator is the source of truth (LAW 3).** Any tier change edits the
   `model-allocation.md` table and **re-runs `python3 scripts/gen_subagents.py` until
   `git diff` is clean**; dispatch passes `model` **explicitly** every time (frontmatter is
   unreliable — claude-code#44385). A tier change with a dirty `gen_subagents` diff is not
   done.
5. **T4 is a consequence, capped by T7.** "≥ 25% haiku share" is the *result* of correct
   routing, not a quota to hit by down-tiering quality-bearing work. **If a quality
   regression appears on the fixed eval/gate suite, routing tightens and T4 yields**
   (applied to the static re-tier). T7 overrides T4.

## Consequences

**Positive:** mechanical tail runs at haiku speed/cost → shorter waves (the slowest-model
effect shrinks) and lower tokens/$ per action (T4, contributes to T10); the opus floor
keeps every gate, ADR, and security review at full capability — **no quality is traded for
the cheap-tier share**.

**Negative / accepted:** the boundary is a **judgement** that must be re-checked as roles
evolve; a too-aggressive down-tier shows up as an eval regression and is reverted (rollback,
not waiver). Until routing-mix data is available, re-tier decisions lean conservative
(data-driven, default no-change), so the haiku share target may initially be
**CAPPED-by-evidence** — stated honestly rather than forced.

**Law check:** LAW 3 (explicit `model` per dispatch; `gen_subagents.py` clean; gate/
architecture/security stay opus); LAW 2 (a re-tiered agent still passes through a real,
distinct-reviewer gate — re-tiering never converts a gate into a rubber-stamp); T7 governor.

## Enforcement / acceptance (handed to DAS-1366)

- Concrete `model-allocation.md` edits + `gen_subagents.py` rerun with **clean `git diff`**;
  the ADR delta (which roles/subtasks moved and the data behind it) recorded on DAS-1366.
- Eval/gate pass-rate on the fixed suite is **no worse** than pre-re-tier (T7); every
  routing decision auditable.
- Haiku share measured at GATE-4/GATE-6 (T4), annotated ACHIEVED / STRETCH / CAPPED-by-X.
