---
id: DAS-1471
title: Guardrail tripwires per role with dispatch retry-with-feedback
status: done
assignee: cto
author: ceo
dept: engineering
priority: p1
parent: DAS-1463
goal: organism-ws2-loom
depends_on: [DAS-1464]
zone: guardrails
created: 2026-07-03
updated: 2026-07-03
---

## Description

**What.** Add a per-role guardrail layer plus a dispatch wrapper that turns a
guardrail trip into a self-correcting retry loop. Each role gets an INPUT
guardrail (screens a ticket's scope before the agent accepts it) and an OUTPUT
guardrail (screens the agent's produced work before it is accepted). A tripped
OUTPUT guardrail writes structured feedback back into the ticket and
re-dispatches the SAME agent (bounded retries), then escalates per the routing
chain if the agent still cannot satisfy the guardrail.

**Why.** GATE-3 (P10) of the ORGANISM WS2 LOOM program calls for a closed-loop
"tripwire" so a wrong-scope or wrong-output dispatch does not silently ship or
stall — it either self-corrects within a hard retry bound or escalates to a
human/manager review, never looping unboundedly and never passing bad work
through.

**Embedded context.**
- Spec-of-record: `docs/research/ORGANISM-PROGRAM-PLAN.md` (ORGANISM WS2 LOOM,
  GATE-3 / P10). Parent epic: DAS-1463. Depends on DAS-1464 (must be `done`
  before this ticket is actionable — dep-blocked skip in `/daslab-cycle` step 3).
- Escalation chain is `board/ROUTING.md`: each role's "Reports to (reviewer)"
  column is the escalation target. `security-lead` reports to `cto`; a manager
  who is also the author escalates one level up (ultimately CTO/CEO). The
  `in_review` reassignment rule ("assignee == author → author's manager") is the
  same chain used here for escalation after exhausted retries.
- The dispatch wrapper is documented — not just implemented — in the
  `/daslab-cycle` SKILL.md dispatch section (step 5c, "Spawn the subagent").
  That skill has a byte-stable prompt-cache prefix guarded by
  `scripts/check_cache_prefix.py` with `CACHE_PREFIX_VERSION` (currently
  `v15-organism-evidence-snapshot`, line ~630). If the edit touches the
  stable-prefix region, bump `CACHE_PREFIX_VERSION` and run
  `python3 scripts/check_cache_prefix.py --fix`; the guardrail-wrapper prose
  should live in the dynamic-tail / dispatch-procedure area (step 5), NOT in the
  frozen stable prefix, so ideally no bump is needed — verify with the checker.
- Feedback origin tag: an OUTPUT-guardrail-triggered ticket edit is written into
  the ticket `## Log` with `origin: output_guardrail` so the re-dispatched agent
  (and later readers) can tell guardrail feedback apart from human review notes.
- INPUT guardrail failure modes to screen: wrong-department (ticket `dept` does
  not match the role's dept per `board/ROUTING.md`), missing `consumes`/inputs
  the ticket declares it needs, and gate-open violations (AADL predecessor gate
  or `depends_on` not `done`) — the agent refuses the ticket before accepting.

**Extend vs. new.**
- **New** package `governance/guardrails/` holding one module per role
  (`governance/guardrails/<role>.py`), each exposing a callable returning
  `(ok: bool, feedback: str)`. Provide at least a couple of concrete example
  role guardrails (e.g. `security-lead`, `backend-eng-1`), plus a shared
  base/protocol and a `runner` that loads a role's guardrail and evaluates it.
- **New** dispatch-wrapper logic (a script under `scripts/` — e.g.
  `scripts/guardrail_dispatch.py` — reusing existing helpers) that: runs the
  INPUT guardrail before accept, runs the OUTPUT guardrail after work, writes
  feedback (`origin: output_guardrail`) into the ticket on a trip, re-dispatches
  the same agent up to a max of 2 retries, then escalates via `board/ROUTING.md`.
- **Extend** `.claude/skills/daslab-cycle/SKILL.md` dispatch section (step 5) to
  document the wrapper contract (input screen → accept → output screen →
  retry-with-feedback max 2 → escalate). Reuse the routing map already parsed in
  step 2/`board/ROUTING.md`; do not re-invent the reviewer lookup.
- Reuse existing patterns: role keys/escalation come from `board/ROUTING.md`
  (parsed by `scripts/board_lint.py::load_known_roles`); do NOT hard-code role
  lists. Follow the tolerant-frontmatter-read pattern used elsewhere.

**Key files (paths).**
- `governance/guardrails/__init__.py` — package + base protocol `(ok, feedback)`.
- `governance/guardrails/<role>.py` — example per-role guardrails.
- `governance/guardrails/runner.py` — load + evaluate a role's guardrail.
- `scripts/guardrail_dispatch.py` — INPUT/OUTPUT wrapper + retry/escalate loop.
- `.claude/skills/daslab-cycle/SKILL.md` — document the wrapper (step 5 dispatch).
- `board/ROUTING.md` — escalation/reviewer chain (read-only reference).
- `scripts/board_lint.py` — role-key + frontmatter reader to reuse.
- `scripts/check_cache_prefix.py` / `CACHE_PREFIX_VERSION` — cache-prefix guard.
- `tests/test_guardrail_*.py` — new tests (failing-ticket self-correct/escalate).

## Acceptance criteria

- [x] `governance/guardrails/<role>.py` modules each expose a callable returning
      `(ok, feedback)`; at least two concrete example role guardrails ship with a
      shared base/protocol and a `runner`.
- [x] OUTPUT-guardrail trip writes feedback into the ticket (log entry tagged
      `origin: output_guardrail`) and re-dispatches the SAME agent, bounded to a
      maximum of 2 retries.
- [x] After 2 exhausted retries the wrapper escalates per `board/ROUTING.md`
      (the failing role's reviewer; manager-is-author → one level up to CTO/CEO).
- [x] INPUT guardrail screens ticket scope before accept — rejects
      wrong-department, missing `consumes`/required inputs, and gate-open
      (`depends_on`/AADL predecessor not `done`) violations.
- [x] A deliberately failing test ticket self-corrects within ≤2 retries OR
      escalates — proven by a test (`tests/test_guardrail_*.py`).
- [x] The `/daslab-cycle` SKILL.md dispatch section documents the wrapper
      contract (input screen → accept → output screen → retry-with-feedback max 2
      → escalate).
- [x] `python3 scripts/check_cache_prefix.py` exits 0 if SKILL.md was touched
      (bump `CACHE_PREFIX_VERSION` + `--fix` only if the stable-prefix region
      changed; prefer keeping the new prose out of the stable prefix).
- [x] Full test suite: 0 failed; diagnostics 100/100.
- [x] Org-engine ticket only — NO `project:` field (board_lint R9); no other
      file created by this planning step.

## Log

### 2026-07-03 — CEO
Created from ORGANISM WS2 LOOM decomposition (/daslab-plan). Spec-of-record: docs/research/ORGANISM-PROGRAM-PLAN.md.
Scope = GATE-3 (P10): per-role `governance/guardrails/<role>.py` returning `(ok, feedback)`; a dispatch wrapper where an OUTPUT-guardrail trip writes feedback into the ticket (`origin: output_guardrail`) and re-dispatches the SAME agent (max 2 retries) then escalates per `board/ROUTING.md`; INPUT guardrails screen ticket scope before accept (wrong-department, missing consumes, gate-open violations). Wrapper documented in the `/daslab-cycle` SKILL.md dispatch section (bump `CACHE_PREFIX_VERSION` + `check_cache_prefix --fix` only if the stable-prefix region changes). Ships example role guardrails + runner + tests (a deliberately failing ticket self-corrects within 2 retries or escalates).
depends_on DAS-1464 — not actionable until DAS-1464 is `done` (dep-blocked skip). Assigned to security-lead (engineering); reviewer/escalation = CTO per board/ROUTING.md.

### 2026-07-03 — Security Lead
Implemented the GATE-3 / P10 guardrail tripwire (DAS-1464 confirmed `done`, so dep-gate clear). Shipped:
- `governance/guardrails/__init__.py` — package + `(ok, feedback)` contract (`GuardrailResult`), `GuardrailContext` dataclass, `Guardrail` Protocol, and the shared `default_input_guardrail` (wrong-department / missing-`consumes` / gate-open screens) + `default_output_guardrail` (empty / unresolved-marker). Pure logic, no IO.
- `governance/guardrails/security-lead.py` and `governance/guardrails/backend-eng-1.py` — the two example role modules, each exposing `input_guardrail(ctx)` / `output_guardrail(ctx)`. security-lead adds a security-relevance INPUT screen + a sign-off/leaked-secret OUTPUT screen; backend-eng-1 adds a test-evidence/green-build OUTPUT screen.
- `governance/guardrails/runner.py` — loads `<role>.py` BY FILE PATH (hyphenated keys work), transparent `default_*` fallback for any role with no bespoke module, ROUTING role-table parser (role→dept), and `build_context` (reads ticket + board dep statuses; tolerant frontmatter reader mirrors `board_lint.parse_frontmatter`).
- `scripts/guardrail_dispatch.py` — the wrapper: INPUT screen (pre-accept, refuse+re-route on trip) → accept → run agent → OUTPUT screen → on trip write feedback into `## Log` tagged `origin: output_guardrail` + re-dispatch the SAME agent (bounded max 2 retries) → escalate per `board/ROUTING.md` (reviewer chain; manager-is-author climbs one level). `run_agent` is injected so the loop is deterministic + testable; only side effect is the ticket file. CLI runs the INPUT scope screen standalone.
- `.claude/skills/daslab-cycle/SKILL.md` — new dispatch sub-step **5g** documents the wrapper contract (input screen → accept → output screen → retry-with-feedback max 2 → escalate). Prose sits in step 5 which is inside the ADR-0006 stable-prefix region, so bumped `CACHE_PREFIX_VERSION` v15-organism-evidence-snapshot → **v16-guardrail-tripwire** and ran `check_cache_prefix.py --fix` in the same commit (prose carries no volatile tokens — DAS-ids/timestamps/wave-counters — so the volatile-token gate stays clean).
- Tests: `tests/test_guardrail_roles.py` (23) + `tests/test_guardrail_dispatch.py` (6). Prove: a deliberately failing ticket SELF-CORRECTS within ≤2 retries, and one that never satisfies ESCALATES (security-lead → cto) with the ticket reassigned + `in_review` + no self-review.
VERIFY (full, from worktree): `pytest -q` = 1134 passed / 1 skipped / 0 failed; `diagnostics.py` = 100/100; `board_lint.py` = 0; `ruff check scripts tests` = clean; `check_cache_prefix.py` = exit 0. Committed LOCAL on branch `feat/das-1471-guardrails` (strict local-only — NOT pushed). Status → `in_review`, reviewer = CTO per board/ROUTING.md.

### 2026-07-03 — Orchestrator (/daslab-cycle collect)
Done via local-only done-gate: full suite 1201 pass + validators green + merge verification. governance/guardrails/<role>.py (ok,feedback) + guardrail_dispatch.py wrapper (retry-with-feedback max2 then escalate) + SKILL 5g (cache v16); security-relevant, contract documented+tested, live-wiring is a follow-up.
