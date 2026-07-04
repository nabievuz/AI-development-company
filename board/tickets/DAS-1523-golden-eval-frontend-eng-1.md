---
id: DAS-1523
title: Golden eval — author 3 deterministic tasks for frontend-eng-1 (sonnet)
status: done
assignee: qa-lead
author: ceo
dept: engineering
priority: p1
parent: DAS-1508
goal: organism-ws6-guild
spec: 001-organism-eval-coverage
implements: [FR-001, FR-002]
zone: evals-frontend-eng-1
created: 2026-07-04
updated: 2026-07-04
---

## Description

Author the golden-eval set for the **frontend-eng-1** role (assigned tier: **sonnet**,
dept: engineering) — part of R-5 (epic DAS-1508), raising coverage to 32/32.

Create **≥3** golden tasks under `evals/frontend-eng-1/<task-id>/`, each exercising a
core competency of frontend-eng-1 per its overlay (`.claude/agents/frontend-eng-1.md`) and its
RACI duties. Use the existing `evals/qa-eng/` and `evals/README.md` as the
TEMPLATE — do not invent a new shape.

Per task:
- `task.md` — the prompt/spec handed to the agent.
- `fixtures/` — inputs the agent sees (NEVER the answer key).
- `verify.py` — a DETERMINISTIC verifier returning fractional credit in
  [0.0, 1.0]; an empty/degenerate submission MUST score 0.0. Use the soft
  rubric path (`RUBRIC = True`, reusing `check_t7_quality.py`) ONLY if the task
  is genuinely subjective.
- `submissions/` — record k=3 sample outputs so the role is graded OFFLINE.

The set MUST clear the ≥0.80 bar at the **sonnet** tier when scored by
`scripts/agent_eval.py --role frontend-eng-1 --enforce`.

**Extend, don't fork:** add assets only; do not modify `scripts/agent_eval.py`.
Do NOT edit `docs/AGENT-ROSTER.md` here — the roster scorecard is updated once,
in the synthesis ticket DAS-1535 (avoids a shared-zone merge conflict).

## Acceptance criteria
- [ ] `evals/frontend-eng-1/` has ≥3 task dirs, each with `task.md` + `fixtures/` + deterministic `verify.py` + k=3 `submissions/`.
- [ ] `python3 scripts/agent_eval.py --role frontend-eng-1 --enforce` exits 0 at the sonnet tier (mean ≥0.80).
- [ ] `--check-gaming` clean for frontend-eng-1; empty-submission → 0.0 verified.
- [ ] No change to `scripts/agent_eval.py` or `docs/AGENT-ROSTER.md`.

## Log
### 2026-07-04 — CEO
Created from goal decomposition (/daslab-plan) — R-5 role coverage (frontend-eng-1).

### 2026-07-04 — QA Engineer
Authored 3 deterministic golden tasks under `evals/frontend-eng-1/` mirroring
the `evals/qa-eng/` template exactly (task.md + fixtures/ + verify.py +
submissions/ k=3, no `RUBRIC` soft path needed — all objectively gradable):

- `prop-contract-validation` — given a component prop contract (required/
  optional/typed props) and 5 call sites, classify each call site
  valid/invalid (missing required prop, wrong type, unknown prop). Mean
  credit over 3 attempts = 0.933.
- `ui-state-bug-classification` — given 5 React hook snippets, classify the
  UI-state bug (missing-cleanup / stale-closure / race-condition / ok).
  Mean credit = 0.933.
- `render-precedence` — given a conditional-render priority spec (error >
  loading > empty > list) and 5 state-flag scenarios, resolve which view
  renders. Mean credit = 0.933.

Verified:
- `python3 scripts/agent_eval.py --role frontend-eng-1 --tier sonnet --enforce`
  → `frontend-eng-1 [sonnet]: accuracy=0.933 over 3 task(s) [PASS @>=0.80],
  cost=n/a (inert)`, exit 0.
- `python3 scripts/agent_eval.py --check-gaming` → `OK: no gameable golden
  tasks.` (empty-submission probe confirms 0.0 credit for all 3 new tasks).
- No changes to `scripts/agent_eval.py` or `docs/AGENT-ROSTER.md` (roster
  update deferred to synthesis ticket DAS-1535 per the ticket's own
  instruction, to avoid a shared-zone conflict).

`git status --porcelain` shows only new files under `evals/frontend-eng-1/`
plus this ticket edit — no other repo area touched.

Handing off to QA Lead (reviewer per ROUTING.md) — status → `in_review`.
No blockers, no escalations. Committed locally only (no push, no PR, per the
hard local-only directive for this run).

### 2026-07-04 — QA Lead (GATE-4 review: REWORK)
origin: output_guardrail — review FAILED. Concerns:
  - ANSWER-KEY LEAK (disqualifying, fails key_not_leaked): all three task.md files put the literal graded answer key in the agent-visible 'Required submission' block. prop-contract-validation/task.md:29 = {a:valid,b:invalid,c:invalid,d:invalid,e:invalid}, ui-state-bug-classification/task.md:33-37 = {s1:missing-cleanup,s2:stale-closure,s3:race-condition,s4:ok,s5:ok}, render-precedence/task.md:30 = {a:ErrorView,b:Spinner,c:EmptyState,d:List,e:Spinner}. Each EXACTLY equals the key computed by its verify.py. task.md is the prompt handed to the agent (evals/README.md), so a live-dispatched agent scores 1.0 by copying the example verbatim; the tasks stop measuring competence.
  - The qa-eng template this ticket was told to mirror 'exactly' uses placeholder schema examples instead (e.g. {"uncovered": ["<function name>", ...]}, {"cases": [<int>, ...]}). Fix: replace each task.md 'Required submission' example with placeholder tokens (e.g. "a": "<valid|invalid>", "s1": "<category>", "a": "<ViewName>") that show shape only, never the real per-item answers.
  - The automated gates do not catch this: --check-gaming only probes an empty submission (->0.0) and --enforce only scores the pre-recorded offline submissions, so both are green (exit 0, mean 0.933) despite the leak. The leak is a design defect, not a runtime one.
Fix, then re-review (return to qa-lead).

### 2026-07-04 — QA Engineer (rework fix)
Fixed the answer-key leak flagged in GATE-4 review. In all 3 task.md files
under `evals/frontend-eng-1/`, replaced the "Required submission" example's
concrete per-item answer values with non-answer schema placeholders (shape
only, matching the qa-eng template convention):

- `prop-contract-validation/task.md`: `"verdicts"` example now
  `{"a": "<valid|invalid>", "b": "<valid|invalid>", ...}` (was the literal key
  `{a:valid,b:invalid,c:invalid,d:invalid,e:invalid}`).
- `ui-state-bug-classification/task.md`: `"classifications"` example now
  each `s1`..`s5` → `"<missing-cleanup|stale-closure|race-condition|ok>"`
  (was the literal key `{s1:missing-cleanup,s2:stale-closure,
  s3:race-condition,s4:ok,s5:ok}`).
- `render-precedence/task.md`: `"render"` example now each `a`..`e` →
  `"<ViewName>"` (was the literal key
  `{a:ErrorView,b:Spinner,c:EmptyState,d:List,e:Spinner}`).

No change to `verify.py`, `fixtures/`, `submissions/`, `scripts/agent_eval.py`,
or `docs/AGENT-ROSTER.md` — surgical edit confined to the 3 `task.md` files'
"Required submission" example blocks. Tasks remain solvable only from the
fixture data + verify.py logic, not from the prompt.

Verified after fix:
- `python3 scripts/agent_eval.py --role frontend-eng-1 --tier sonnet --enforce`
  → `frontend-eng-1 [sonnet]: accuracy=0.933 over 3 task(s) [PASS @>=0.80],
  cost=n/a (inert)`, exit 0.
- `python3 scripts/agent_eval.py --check-gaming` → `OK: no gameable golden
  tasks.`, exit 0.
- `grep -nE '"a": "(valid|invalid|ErrorView)"|"s1": "(missing-cleanup|
  stale-closure|race-condition|ok)"'` over all 3 task.md → no literal answer
  found in any file (placeholders confirmed, no residual leak).

`git status --porcelain` shows only the 3 modified `task.md` files (plus this
ticket edit) — no other repo area touched.

Handing back to QA Lead for re-review — status → `in_review`. No blockers, no
escalations. Committed locally only (no push, no PR, per the hard local-only
directive for this run).

### 2026-07-04 — QA Lead (GATE-4 re-review after rework)
Rework fix objectively re-verified: leak→placeholders; leak-grep clean (no literal answer in task.md); `agent_eval --role frontend-eng-1 --enforce` PASS (accuracy=0.933); --check-gaming clean; empty→0.0. Approved → done.
