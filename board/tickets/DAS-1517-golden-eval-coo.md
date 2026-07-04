---
id: DAS-1517
title: Golden eval — author 3 deterministic tasks for coo (sonnet)
status: done
assignee: qa-lead
author: ceo
dept: engineering
priority: p1
parent: DAS-1508
goal: organism-ws6-guild
spec: 001-organism-eval-coverage
implements: [FR-001, FR-002]
zone: evals-coo
created: 2026-07-04
updated: 2026-07-04
branch: feat/das-1517-golden-eval-coo
---

## Description

Author the golden-eval set for the **coo** role (assigned tier: **sonnet**,
dept: operations) — part of R-5 (epic DAS-1508), raising coverage to 32/32.

Create **≥3** golden tasks under `evals/coo/<task-id>/`, each exercising a
core competency of coo per its overlay (`.claude/agents/coo.md`) and its
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
`scripts/agent_eval.py --role coo --enforce`.

**Extend, don't fork:** add assets only; do not modify `scripts/agent_eval.py`.
Do NOT edit `docs/AGENT-ROSTER.md` here — the roster scorecard is updated once,
in the synthesis ticket DAS-1535 (avoids a shared-zone merge conflict).

## Acceptance criteria
- [ ] `evals/coo/` has ≥3 task dirs, each with `task.md` + `fixtures/` + deterministic `verify.py` + k=3 `submissions/`.
- [ ] `python3 scripts/agent_eval.py --role coo --enforce` exits 0 at the sonnet tier (mean ≥0.80).
- [ ] `--check-gaming` clean for coo; empty-submission → 0.0 verified.
- [ ] No change to `scripts/agent_eval.py` or `docs/AGENT-ROSTER.md`.

## Log
### 2026-07-04 — CEO
Created from goal decomposition (/daslab-plan) — R-5 role coverage (coo).

### 2026-07-04 — QA Engineer
Authored `evals/coo/` (3 deterministic golden tasks, ≥3 per acceptance bar),
mirroring `evals/qa-eng/` and `evals/README.md` exactly — no new shape
invented, `scripts/agent_eval.py` and `docs/AGENT-ROSTER.md` untouched
(verified via `git diff --stat` — no output on either path).

Tasks (each: `task.md` + `fixtures/` + deterministic `verify.py` + k=3
`submissions/`), chosen to cover distinct coo/RACI competencies per
`.claude/agents/coo.md` + `operations/CLAUDE.md`:
- `vendor-renewal-risk` — vendor contract renewal risk flagging (Authority:
  "Approve vendor contracts"). Set-based credit
  (TP - FP)/|expected|, mirrors qa-eng/coverage-gap.
- `sla-gate-decision` — release-gate compliance decision (Authority: "Block
  any release with unresolved compliance issues"). Two-part credit: 0.5 for
  the block/no-block boolean, 0.5 for the blocking-issue-id set.
- `budget-allocation` — cross-department budget/resource trade-off (greedy
  priority-ordered full-fund-or-skip allocation under a fixed cap). Set-based
  credit, same formula as vendor-renewal-risk.

All three: fixture is the agent-visible input only, answer key lives solely
in `verify.py`, k=3 identical-correct sample submissions recorded (offline
grading, no live subagent dispatch).

Verification run (from the worktree):
```
$ python3 scripts/agent_eval.py --role coo --tier sonnet --enforce
coo [sonnet]: accuracy=1.000 over 3 task(s) [PASS @>=0.80], cost=n/a (inert)
EXIT=0

$ python3 scripts/agent_eval.py --check-gaming
OK: no gameable golden tasks.
EXIT=0
```
Empty-submission probe (`degenerate_credit`) confirmed `0.0` for all three
tasks (`budget-allocation`, `sla-gate-decision`, `vendor-renewal-risk`).

`git status --porcelain` shows only `evals/coo/` as new/untracked; no diff
against `scripts/agent_eval.py` or `docs/AGENT-ROSTER.md`.

Handing to QA Lead for review (never-review-own-work rule) — status →
`in_review`, assignee → `qa-lead`. Committed locally only on branch
`feat/das-1517-golden-eval-coo`; no push, no PR (per this ticket's
local-only constraint).

### 2026-07-04 — QA Lead (GATE-4 review)
Reviewed independently (adversarial). enforce PASS (accuracy=1), deterministic verifiers, empty→0.0, answer-key not leaked, tasks meaningful & distinct. Approved → done.
