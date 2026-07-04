---
id: DAS-1518
title: Golden eval — author 3 deterministic tasks for cpo (opus)
status: done
assignee: qa-lead
author: ceo
dept: engineering
priority: p1
parent: DAS-1508
goal: organism-ws6-guild
spec: 001-organism-eval-coverage
implements: [FR-001, FR-002]
zone: evals-cpo
created: 2026-07-04
updated: 2026-07-04
---

## Description

Author the golden-eval set for the **cpo** role (assigned tier: **opus**,
dept: product) — part of R-5 (epic DAS-1508), raising coverage to 32/32.

Create **≥3** golden tasks under `evals/cpo/<task-id>/`, each exercising a
core competency of cpo per its overlay (`.claude/agents/cpo.md`) and its
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
`scripts/agent_eval.py --role cpo --enforce`.

**Extend, don't fork:** add assets only; do not modify `scripts/agent_eval.py`.
Do NOT edit `docs/AGENT-ROSTER.md` here — the roster scorecard is updated once,
in the synthesis ticket DAS-1535 (avoids a shared-zone merge conflict).

## Acceptance criteria
- [ ] `evals/cpo/` has ≥3 task dirs, each with `task.md` + `fixtures/` + deterministic `verify.py` + k=3 `submissions/`.
- [ ] `python3 scripts/agent_eval.py --role cpo --enforce` exits 0 at the opus tier (mean ≥0.80).
- [ ] `--check-gaming` clean for cpo; empty-submission → 0.0 verified.
- [ ] No change to `scripts/agent_eval.py` or `docs/AGENT-ROSTER.md`.

## Log
### 2026-07-04 — CEO
Created from goal decomposition (/daslab-plan) — R-5 role coverage (cpo).

### 2026-07-04 — QA Engineer
Authored `evals/cpo/` golden-eval set (3 deterministic tasks), mirroring
`evals/README.md` + `evals/qa-eng/` shape exactly:

- `roadmap-prioritization-rice/` — RICE-scored roadmap selection under an
  engineering-capacity constraint (knapsack-style trade-off). Verifier
  brute-forces the capacity-feasible optimum and scores
  `achieved_value / optimal_value`; a capacity-violating submission scores 0.
- `feature-tradeoff-risk-budget/` — greenlight decision under BOTH a budget
  cap and a high-risk-count cap (two simultaneous constraints force a real
  trade-off, not just a value sort). Same brute-force-optimum scoring shape.
- `sunset-decision/` — feature-cut judgment: sunset only when a feature is
  BOTH low-adoption AND running negative margin. Precision/recall-style
  credit identical to `evals/qa-eng/coverage-gap`'s pattern.

Each task ships `task.md` + `fixtures/` (inputs only, no answer key) +
deterministic `verify.py` + `submissions/attempt-{1,2,3}.json` (k=3, ranging
strong→partial so the role accuracy is a genuine mean, not a rubber stamp).

Verified locally in the worktree:
- `python3 scripts/agent_eval.py --role cpo --tier opus --enforce` → exit 0,
  accuracy **0.8239** (bar 0.80). Per-task accuracy: roadmap-prioritization-rice
  0.8828, feature-tradeoff-risk-budget 0.8111, sunset-decision 0.7778.
- `python3 scripts/agent_eval.py --check-gaming` → `OK: no gameable golden
  tasks.` (exit 0); every verifier's empty-submission credit is 0.0.
- Confirmed no diff to `scripts/agent_eval.py` or `docs/AGENT-ROSTER.md`
  (`git status --porcelain` clean on both).

Committed locally on `feat/das-1518-golden-eval-cpo` in the DAS-1518 worktree
— no push, no PR (hard local-only per dispatch). Routing to QA Lead for
review per `board/ROUTING.md` (never review own work).

### 2026-07-04 — QA Lead (GATE-4 review)
Reviewed independently (adversarial). enforce PASS (accuracy=0.824), deterministic verifiers, empty→0.0, answer-key not leaked, tasks meaningful & distinct. Approved → done.
