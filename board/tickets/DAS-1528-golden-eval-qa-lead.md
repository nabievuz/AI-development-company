---
id: DAS-1528
title: Golden eval — author 3 deterministic tasks for qa-lead (opus)
status: done
assignee: qa-lead
author: ceo
dept: engineering
priority: p1
parent: DAS-1508
goal: organism-ws6-guild
spec: 001-organism-eval-coverage
implements: [FR-001, FR-002]
zone: evals-qa-lead
created: 2026-07-04
updated: 2026-07-04
---

## Description

Author the golden-eval set for the **qa-lead** role (assigned tier: **opus**,
dept: engineering) — part of R-5 (epic DAS-1508), raising coverage to 32/32.

Create **≥3** golden tasks under `evals/qa-lead/<task-id>/`, each exercising a
core competency of qa-lead per its overlay (`.claude/agents/qa-lead.md`) and its
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
`scripts/agent_eval.py --role qa-lead --enforce`.

**Extend, don't fork:** add assets only; do not modify `scripts/agent_eval.py`.
Do NOT edit `docs/AGENT-ROSTER.md` here — the roster scorecard is updated once,
in the synthesis ticket DAS-1535 (avoids a shared-zone merge conflict).

## Acceptance criteria
- [x] `evals/qa-lead/` has ≥3 task dirs, each with `task.md` + `fixtures/` + deterministic `verify.py` + k=3 `submissions/`.
- [x] `python3 scripts/agent_eval.py --role qa-lead --enforce` exits 0 at the opus tier (mean ≥0.80).
- [x] `--check-gaming` clean for qa-lead; empty-submission → 0.0 verified.
- [x] No change to `scripts/agent_eval.py` or `docs/AGENT-ROSTER.md`.

## Log
### 2026-07-04 — CEO
Created from goal decomposition (/daslab-plan) — R-5 role coverage (qa-lead).

### 2026-07-04 — QA Engineer
Authored the qa-lead (opus) golden-eval set, mirroring `evals/README.md` +
`evals/qa-eng/` exactly (no new shape). Note: I am qa-eng authoring an
INDEPENDENT eval for my manager qa-lead's role — permitted per dispatch (I am
not qa-lead grading myself; the roles are distinct).

Created `evals/qa-lead/` with 3 deterministic tasks, each probing a qa-lead
judgment competency (not just a lookup):
- `gate-decision` — GATE-4 go/no-go release call + blocking reasons from a CI
  snapshot; a flaky test is a deliberate distractor (never itself blocking).
- `review-triage` — merge-blocking triage from PR findings; severity alone is
  insufficient (a `major`/non-security finding is a distractor, not blocking).
- `test-strategy-gap` — missing test-type sign-off by feature risk level
  (low/medium/high → required test-type set), from an existing test plan.

Each task has `task.md`, `fixtures/` (inputs only, no answer key), a
deterministic `verify.py` (precision/recall-style fractional credit, answer
key derived from the fixture inside the verifier, empty submission → 0.0),
and `submissions/` with k=3 recorded attempts of varying quality.

Verified:
- `python3 scripts/agent_eval.py --role qa-lead --tier opus --enforce` →
  `qa-lead [opus]: accuracy=0.833 over 3 task(s) [PASS @>=0.80], cost=n/a
  (inert)`, exit 0.
- `python3 scripts/agent_eval.py --check-gaming` → `OK: no gameable golden
  tasks.`, exit 0 (covers qa-lead's 3 new tasks + all pre-existing tasks).
- `git diff --stat -- scripts/agent_eval.py docs/AGENT-ROSTER.md` → empty; only
  `evals/qa-lead/` was added, per the ticket's "extend, don't fork" constraint
  and to avoid the DAS-1535 synthesis-ticket zone conflict.

Moving to `in_review`, reassigning to QA Lead (my manager / reviewer per
`board/ROUTING.md`) — never self-review.

### 2026-07-04 — CTO (GATE-4 review)
Reviewed independently (adversarial). enforce PASS (accuracy=0.833), deterministic verifiers, empty→0.0, answer-key not leaked, tasks meaningful & distinct. Approved → done.
