---
id: DAS-1522
title: Golden eval — author 3 deterministic tasks for frontend-em (opus)
status: done
assignee: qa-lead
author: ceo
dept: engineering
priority: p1
parent: DAS-1508
goal: organism-ws6-guild
spec: 001-organism-eval-coverage
implements: [FR-001, FR-002]
zone: evals-frontend-em
created: 2026-07-04
updated: 2026-07-04
---

## Description

Author the golden-eval set for the **frontend-em** role (assigned tier: **opus**,
dept: engineering) — part of R-5 (epic DAS-1508), raising coverage to 32/32.

Create **≥3** golden tasks under `evals/frontend-em/<task-id>/`, each exercising a
core competency of frontend-em per its overlay (`.claude/agents/frontend-em.md`) and its
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
`scripts/agent_eval.py --role frontend-em --enforce`.

**Extend, don't fork:** add assets only; do not modify `scripts/agent_eval.py`.
Do NOT edit `docs/AGENT-ROSTER.md` here — the roster scorecard is updated once,
in the synthesis ticket DAS-1535 (avoids a shared-zone merge conflict).

## Acceptance criteria
- [ ] `evals/frontend-em/` has ≥3 task dirs, each with `task.md` + `fixtures/` + deterministic `verify.py` + k=3 `submissions/`.
- [ ] `python3 scripts/agent_eval.py --role frontend-em --enforce` exits 0 at the opus tier (mean ≥0.80).
- [ ] `--check-gaming` clean for frontend-em; empty-submission → 0.0 verified.
- [ ] No change to `scripts/agent_eval.py` or `docs/AGENT-ROSTER.md`.

## Log
### 2026-07-04 — CEO
Created from goal decomposition (/daslab-plan) — R-5 role coverage (frontend-em).

### 2026-07-04 — QA Engineer
Authored the frontend-em golden-eval set, mirroring `evals/qa-eng/` and
`evals/README.md` exactly (task.md + fixtures/ + deterministic verify.py +
k=3 submissions/ per task, `fixtures/` vs `submissions/` anti-gaming split
respected — answer key lives only in verify.py).

Three tasks under `evals/frontend-em/`, each grounded in a real frontend-em
competency:
- `component-prop-drilling` — frontend team technical review (flags a
  prop-drilling architecture smell: `prop_drill_depth >= 3` and no
  context/composition remediation).
- `code-split-boundary` — UI architecture decision (lazy-load boundary call:
  `initial_bundle_kb > 150` and not on the critical render path).
- `escalation-triage` — escalation judgment, directly modeled on this role's
  own "When to escalate" policy in `engineering/agents/frontend-em/AGENTS.md`
  (charter-authority overrun, cross-dept impact, or stuck > 1 wave →
  escalate to CTO; otherwise decide locally).

All three use the same deterministic scoring shape as the existing roles
(`credit = clamp01((hits - false_positives) / |expected set|)`), so an empty
submission always scores 0.0.

Verified locally (repo root = this worktree):
- `python3 scripts/agent_eval.py --role frontend-em --tier opus --enforce` →
  `frontend-em [opus]: accuracy=0.852 over 3 task(s) [PASS @>=0.80],
  cost=n/a (inert)`, exit 0.
- `python3 scripts/agent_eval.py --check-gaming` → `OK: no gameable golden
  tasks.`, exit 0. Also confirmed directly via `degenerate_credit()` for all
  3 tasks: each returns `0.0`.
- `git status --porcelain` / `git diff --stat -- scripts/agent_eval.py
  docs/AGENT-ROSTER.md` → only `evals/frontend-em/` is new; the harness
  script and the roster doc are untouched (roster update is DAS-1535's job,
  per the ticket's own instruction).

Moving to `in_review`, assignee → QA Lead (my reviewer per ROUTING.md — I
never review my own work). No escalation needed; no cross-role work
discovered. Committed locally only, no push/PR (hard local-only directive).

### 2026-07-04 — QA Lead (GATE-4 review)
Reviewed independently (adversarial). enforce PASS (accuracy=0.852), deterministic verifiers, empty→0.0, answer-key not leaked, tasks meaningful & distinct. Approved → done.
