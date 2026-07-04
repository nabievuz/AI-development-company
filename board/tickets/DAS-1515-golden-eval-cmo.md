---
id: DAS-1515
title: Golden eval — author 3 deterministic tasks for cmo (sonnet)
status: done
assignee: qa-lead
author: ceo
dept: engineering
priority: p1
parent: DAS-1508
goal: organism-ws6-guild
spec: 001-organism-eval-coverage
implements: [FR-001, FR-002]
zone: evals-cmo
created: 2026-07-04
updated: 2026-07-04
---

## Description

Author the golden-eval set for the **cmo** role (assigned tier: **sonnet**,
dept: marketing) — part of R-5 (epic DAS-1508), raising coverage to 32/32.

Create **≥3** golden tasks under `evals/cmo/<task-id>/`, each exercising a
core competency of cmo per its overlay (`.claude/agents/cmo.md`) and its
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
`scripts/agent_eval.py --role cmo --enforce`.

**Extend, don't fork:** add assets only; do not modify `scripts/agent_eval.py`.
Do NOT edit `docs/AGENT-ROSTER.md` here — the roster scorecard is updated once,
in the synthesis ticket DAS-1535 (avoids a shared-zone merge conflict).

## Acceptance criteria
- [x] `evals/cmo/` has ≥3 task dirs, each with `task.md` + `fixtures/` + deterministic `verify.py` + k=3 `submissions/`.
- [x] `python3 scripts/agent_eval.py --role cmo --enforce` exits 0 at the sonnet tier (mean ≥0.80).
- [x] `--check-gaming` clean for cmo; empty-submission → 0.0 verified.
- [x] No change to `scripts/agent_eval.py` or `docs/AGENT-ROSTER.md`.

## Log
### 2026-07-04 — CEO
Created from goal decomposition (/daslab-plan) — R-5 role coverage (cmo).

### 2026-07-04 — QA Engineer
Authored 3 deterministic golden tasks under `evals/cmo/` (mirroring
`evals/README.md` + `evals/qa-eng/` + `evals/seo-specialist/` shape exactly;
no changes to `scripts/agent_eval.py` or `docs/AGENT-ROSTER.md`):

- `cac-underperformer-flagging` — flag channels whose actual CAC
  (spend/conversions) exceeds `target_cac`; set precision/recall credit.
- `brand-voice-violation-audit` — flag copy snippets violating brand voice
  (banned superlative phrase / multiple exclamation marks / all-caps
  shouting word); set precision/recall credit.
- `roas-budget-reallocation` — cut channels below ROAS 2.0 to 0, split
  `total_budget` proportionally to ROAS across kept channels; per-channel
  5%-of-budget tolerance credit.

Each task ships `task.md`, `fixtures/` (inputs only, no answer key), a
deterministic `verify.py` (score derived independently from the fixture,
never spelled out to the agent), and k=3 recorded `submissions/`.

Verification run in the worktree:
```
$ python3 scripts/agent_eval.py --role cmo --tier sonnet --enforce
cmo [sonnet]: accuracy=0.903 over 3 task(s) [PASS @>=0.80], cost=n/a (inert)
EXIT=0

$ python3 scripts/agent_eval.py --check-gaming
OK: no gameable golden tasks.
EXIT=0
```
Empty-submission → 0.0 is exercised directly by `--check-gaming` (it probes
every task, including the 3 new cmo tasks, with a degenerate `{}`
submission and fails on any credit > 0 — clean here).

`git status --porcelain` confirms only `evals/cmo/` is new/untracked; no
diff to `scripts/agent_eval.py` or `docs/AGENT-ROSTER.md`.

Moving `status: todo → in_review`, routed to QA Lead (reviewer) per
`board/ROUTING.md` — I do not review my own work. Committed locally on
`feat/das-1515-golden-eval-cmo` in the DAS-1515 worktree; NOT pushed
(hard local-only directive).

### 2026-07-04 — QA Lead (GATE-4 review)
Reviewed independently (adversarial). enforce PASS (accuracy=0.903), deterministic verifiers, empty→0.0, answer-key not leaked, tasks meaningful & distinct. Approved → done.
