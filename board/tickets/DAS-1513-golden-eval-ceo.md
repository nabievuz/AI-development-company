---
id: DAS-1513
title: Golden eval — author 3 deterministic tasks for ceo (opus)
status: done
assignee: qa-lead
author: ceo
dept: engineering
priority: p1
parent: DAS-1508
goal: organism-ws6-guild
spec: 001-organism-eval-coverage
implements: [FR-001, FR-002]
zone: evals-ceo
created: 2026-07-04
updated: 2026-07-04
---

## Description

Author the golden-eval set for the **ceo** role (assigned tier: **opus**,
dept: governance) — part of R-5 (epic DAS-1508), raising coverage to 32/32.

Create **≥3** golden tasks under `evals/ceo/<task-id>/`, each exercising a
core competency of ceo per its overlay (`.claude/agents/ceo.md`) and its
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
`scripts/agent_eval.py --role ceo --enforce`.

**Extend, don't fork:** add assets only; do not modify `scripts/agent_eval.py`.
Do NOT edit `docs/AGENT-ROSTER.md` here — the roster scorecard is updated once,
in the synthesis ticket DAS-1535 (avoids a shared-zone merge conflict).

## Acceptance criteria
- [ ] `evals/ceo/` has ≥3 task dirs, each with `task.md` + `fixtures/` + deterministic `verify.py` + k=3 `submissions/`.
- [ ] `python3 scripts/agent_eval.py --role ceo --enforce` exits 0 at the opus tier (mean ≥0.80).
- [ ] `--check-gaming` clean for ceo; empty-submission → 0.0 verified.
- [ ] No change to `scripts/agent_eval.py` or `docs/AGENT-ROSTER.md`.

## Log
### 2026-07-04 — CEO
Created from goal decomposition (/daslab-plan) — R-5 role coverage (ceo).

### 2026-07-04 — QA Engineer
Authored the ceo golden-eval set, mirroring `evals/README.md` + `evals/qa-eng/`
shape exactly (task.md + fixtures/ + deterministic verify.py + submissions/
k=3, no answer key leaked into fixtures). 3 tasks created under `evals/ceo/`,
each exercising a distinct ceo competency:

- `escalation-adjudication` — escalation adjudication (charter-authority vs.
  Chairman escalation rule from the `ceo` role overlay's AGENTS.md §6 binding
  rule). 6 records, classification accuracy scoring.
- `goal-queue-triage` — goal approval (QONUN Founder-Approved Goal Queue law:
  >=10 Founder questions answered or waived, AND an explicit
  APPROVED/TASDIQLANDI signal). 6 records, classification accuracy scoring.
- `resource-allocation` — cross-org resource allocation (tier-waterfall
  budget split across departments under a hard cap). 4 depts, normalized-L1
  fractional credit.

All three verifiers are deterministic (`def verify(submission, fixtures) ->
float`), derive the answer key from the fixture at run time (never spelled
out per-record in task.md), and score an empty/degenerate submission at
`0.0` (confirmed via `degenerate_credit`). k=3 submissions recorded per task
with descending quality (perfect / near-perfect / partial) to model realistic
attempt variance.

Verified locally in the DAS-1513 worktree:
- `python3 scripts/agent_eval.py --role ceo --tier opus --enforce` →
  `ceo [opus]: accuracy=0.856 over 3 task(s) [PASS @>=0.80], cost=n/a (inert)`,
  exit 0.
- `python3 scripts/agent_eval.py --check-gaming` → `OK: no gameable golden
  tasks.`, exit 0 (repo-wide, includes the 3 new ceo tasks).
- Per-task degenerate (empty submission) credit: `escalation-adjudication
  0.0`, `goal-queue-triage 0.0`, `resource-allocation 0.0`.
- Confirmed no diff to `scripts/agent_eval.py` or `docs/AGENT-ROSTER.md` (not
  touched — the roster scorecard update is DAS-1535's job per the ticket
  description).

Status → `in_review`, reassigned to `qa-lead` per `board/ROUTING.md` (never
review own work). Nothing to escalate; no blockers.

### 2026-07-04 — QA Lead (GATE-4 review)
Reviewed independently (adversarial). enforce PASS (accuracy=0.856), deterministic verifiers, empty→0.0, answer-key not leaked, tasks meaningful & distinct. Approved → done.
