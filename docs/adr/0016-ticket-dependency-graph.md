# ADR 0016 — Phase 3: machine-readable ticket dependency graph (`depends_on` + `zone`)

- **Status:** Accepted (2026-06-26, Founder-directed debt paydown; **CTO ratify**; additive, no binding-policy text changed)
- **Date:** 2026-06-26
- **Scope:** Board schema — optional `depends_on:` / `zone:` ticket frontmatter;
  `scripts/check_dependency_graph.py` (+`diagnostics.py`/`ci.yml`); the `/daslab-cycle`
  correctness guard reads `zone:` instead of inferring it.
- **Deciders:** **CTO (ratify);** Founder (directed the build).
- **Relates:** ADR-0014/0015 (clarify gate Phases 1–2 — this is **Phase 3**); ADR-0002
  (enforcement-as-code); ADR-0005 (worktree-per-ticket dispatch).

## Context

The `/daslab-cycle` correctness guard ("never two tickets touching the same repo area in
one wave") currently **infers** repo zones from `parent` + title overlap — a heuristic that
can mis-group, and there is **no machine-readable cross-ticket dependency graph** (a ticket
cannot declare it must wait for another). The diagnostic flagged both as Phase-3 debt.

## Decision

1. **Two optional frontmatter fields.**
   - `depends_on: [DAS-1376, DAS-1377]` — ticket ids that MUST be `done` before this one is
     actionable.
   - `zone: apps/web` — the repo area this ticket mutates; two tickets sharing a `zone` must
     not run in the same wave (the correctness guard, now **read** not inferred).

2. **`/daslab-cycle` correctness guard reads `zone`.** When both tickets in a candidate pair
   declare `zone`, the guard uses the declared zones; it falls back to the parent/title
   heuristic only when a zone is absent (backward-compatible). A ticket with an unsatisfied
   `depends_on` (a listed id not yet `done`) is **not actionable** — skip, count as
   dep-blocked (parallel to the AADL gate-order and clarify-gate skips).

3. **Static validator (`scripts/check_dependency_graph.py`, ADR-0002).**
   - **No dangling deps:** every `depends_on` id is a real ticket on the board.
   - **Acyclic:** the `depends_on` graph has no cycle (a cycle deadlocks dispatch).
   - **Well-formed `zone`:** present-but-empty `zone` is a defect.
   - **CI-safe / dormant:** passes when no ticket uses `depends_on`/`zone` (the state today).
     The "no two same-zone in one wave" rule is a **runtime wave** property (not repo state),
     so — like the clarify circuit-breaker (ADR-0014) — it lives in the skill and is guarded
     against deletion by a skill-token test, not statically enforced.

## Consequences

**Positive.** Dispatch can express real ordering (`depends_on`) and exact conflict zones
(`zone`) instead of inferring them; cycles/typos are caught in CI before they deadlock or
mis-group a wave. Dormant and zero-cost until tickets adopt the fields.

**Negative / accepted.** One more validator on the 100/100 gate; the wave-time same-zone rule
stays a skill directive (runtime, not statically enforceable) — guarded by a token test. The
`/daslab-cycle` stable-prefix edit bumps `CACHE_PREFIX_VERSION` (ADR-0006).

**Law check.** ADR-0002 (validator + failing-case pytest + diagnostics registration). ADR-0005
(complements worktree-per-ticket — zones make the no-conflict guarantee explicit). No
binding-policy text changed; the optional fields are additive (tickets without them lint as before).

## Enforcement / acceptance

- `scripts/check_dependency_graph.py` + failing-case pytest; `diagnostics.py` + `ci.yml` wired.
- `/daslab-cycle` guard reads `zone` + dep-blocked skip (CACHE_PREFIX_VERSION bump + baseline `--fix`).
- `board/README.md` documents `depends_on`/`zone`. README ADR index row. `SCORE = 100/100` preserved.
