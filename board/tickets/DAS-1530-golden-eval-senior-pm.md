---
id: DAS-1530
title: Golden eval — author 3 deterministic tasks for senior-pm (opus)
status: done
assignee: qa-lead
author: ceo
dept: engineering
priority: p1
parent: DAS-1508
goal: organism-ws6-guild
spec: 001-organism-eval-coverage
implements: [FR-001, FR-002]
zone: evals-senior-pm
created: 2026-07-04
updated: 2026-07-04
---

## Description

Author the golden-eval set for the **senior-pm** role (assigned tier: **opus**,
dept: product) — part of R-5 (epic DAS-1508), raising coverage to 32/32.

Create **≥3** golden tasks under `evals/senior-pm/<task-id>/`, each exercising a
core competency of senior-pm per its overlay (`.claude/agents/senior-pm.md`) and its
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

The set MUST clear the ≥0.80 bar at the **opus** tier when scored by
`scripts/agent_eval.py --role senior-pm --enforce`.

**Extend, don't fork:** add assets only; do not modify `scripts/agent_eval.py`.
Do NOT edit `docs/AGENT-ROSTER.md` here — the roster scorecard is updated once,
in the synthesis ticket DAS-1535 (avoids a shared-zone merge conflict).

## Acceptance criteria
- [ ] `evals/senior-pm/` has ≥3 task dirs, each with `task.md` + `fixtures/` + deterministic `verify.py` + k=3 `submissions/`.
- [ ] `python3 scripts/agent_eval.py --role senior-pm --enforce` exits 0 at the opus tier (mean ≥0.80).
- [ ] `--check-gaming` clean for senior-pm; empty-submission → 0.0 verified.
- [ ] No change to `scripts/agent_eval.py` or `docs/AGENT-ROSTER.md`.

## Log
### 2026-07-04 — CEO
Created from goal decomposition (/daslab-plan) — R-5 role coverage (senior-pm).

### 2026-07-04 — QA Engineer
Authored the golden-eval set for `senior-pm` (opus tier), mirroring
`evals/README.md` + `evals/qa-eng/` shape exactly (`task.md` + `fixtures/`
+ deterministic `verify.py` + k=3 `submissions/`). Three tasks, each
exercising a distinct senior-pm competency per `.claude/agents/senior-pm.md`:

- `evals/senior-pm/requirements-decomposition/` — decompose one bundled,
  informal stakeholder thread into discrete atomic requirements; verifier
  does AND-keyword matching per atomic requirement with a padding penalty
  against list-stuffing.
- `evals/senior-pm/prioritization-under-constraints/` — pick the
  highest-value backlog subset under a capacity constraint + dependency
  graph; verifier brute-forces the true optimum (6 items, 2^6 search) and
  scores `achieved/optimal`, `0.0` if infeasible (over capacity or a
  dependency missing).
- `evals/senior-pm/acceptance-criteria-quality/` — write acceptance
  criteria for a story with edge cases implied only by support-ticket
  context; verifier blends 70% scenario-keyword coverage + 30%
  Given/When/Then structure fraction.

All three verifiers are pure-Python, deterministic (no clock/model/
randomness), and answer keys live only in `verify.py` — never in
`fixtures/`. Recorded k=3 submissions per task (9 total) at varying quality
to reflect a realistic accuracy spread, not all 1.0.

Acceptance evidence (run from `/Users/owner/DasLab/.claude/worktrees/DAS-1530`):

```
$ python3 scripts/agent_eval.py --role senior-pm --tier opus --enforce
senior-pm [opus]: accuracy=0.917 over 3 task(s) [PASS @>=0.80], cost=n/a (inert)
exit=0

$ python3 scripts/agent_eval.py --check-gaming
OK: no gameable golden tasks.
exit=0
```

Per-task breakdown (`--json`): `requirements-decomposition` 0.9167,
`prioritization-under-constraints` 0.9412, `acceptance-criteria-quality`
0.8917 → role mean 0.9165, clears the 0.80 GATE-4 bar. Empty-submission
credit verified `0.0` for all three tasks directly via
`degenerate_credit()`.

No changes made to `scripts/agent_eval.py` or `docs/AGENT-ROSTER.md`
(confirmed via `git status --porcelain` — only `evals/senior-pm/` is new/
untracked). Roster scorecard update is deferred to synthesis ticket
DAS-1535 per the ticket's own instruction.

Status → `in_review`, routed to **qa-lead** (my reviewer per
`board/ROUTING.md`) for review/merge. This work is committed LOCALLY only
(worktree `/Users/owner/DasLab/.claude/worktrees/DAS-1530`, no push/PR per
the hard local-only directive for this run).

### 2026-07-04 — QA Lead (GATE-4 review)
Reviewed independently (adversarial). enforce PASS (accuracy=0.9165), deterministic verifiers, empty→0.0, answer-key not leaked, tasks meaningful & distinct. Approved → done.
