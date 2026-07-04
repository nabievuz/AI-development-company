---
id: DAS-1525
title: Golden eval — author 3 deterministic tasks for growth-marketer (sonnet)
status: done
assignee: qa-lead
author: ceo
dept: engineering
priority: p1
parent: DAS-1508
goal: organism-ws6-guild
spec: 001-organism-eval-coverage
implements: [FR-001, FR-002]
zone: evals-growth-marketer
created: 2026-07-04
updated: 2026-07-04
---

## Description

Author the golden-eval set for the **growth-marketer** role (assigned tier: **sonnet**,
dept: marketing) — part of R-5 (epic DAS-1508), raising coverage to 32/32.

Create **≥3** golden tasks under `evals/growth-marketer/<task-id>/`, each exercising a
core competency of growth-marketer per its overlay (`.claude/agents/growth-marketer.md`) and its
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
`scripts/agent_eval.py --role growth-marketer --enforce`.

**Extend, don't fork:** add assets only; do not modify `scripts/agent_eval.py`.
Do NOT edit `docs/AGENT-ROSTER.md` here — the roster scorecard is updated once,
in the synthesis ticket DAS-1535 (avoids a shared-zone merge conflict).

## Acceptance criteria
- [x] `evals/growth-marketer/` has ≥3 task dirs, each with `task.md` + `fixtures/` + deterministic `verify.py` + k=3 `submissions/`.
- [x] `python3 scripts/agent_eval.py --role growth-marketer --enforce` exits 0 at the sonnet tier (mean ≥0.80).
- [x] `--check-gaming` clean for growth-marketer; empty-submission → 0.0 verified.
- [x] No change to `scripts/agent_eval.py` or `docs/AGENT-ROSTER.md`.

## Log
### 2026-07-04 — CEO
Created from goal decomposition (/daslab-plan) — R-5 role coverage (growth-marketer).

### 2026-07-04 — QA Engineer
Authored the golden-eval set for **growth-marketer** (sonnet tier) under
`evals/growth-marketer/`, mirroring the exact shape of `evals/qa-eng/` /
`evals/product-analyst/` per `evals/README.md`. Three deterministic tasks, each
with `task.md` + `fixtures/` (inputs only, no answer key) + `verify.py`
(deterministic, empty-submission-safe) + `submissions/` (k=3):

- `funnel-stage-fix` — largest benchmark-vs-actual conversion gap across an
  acquisition funnel + expected-lift estimate (funnel/conversion analysis).
- `experiment-prioritization` — RICE-score ranking of a growth-experiment
  backlog, pick the highest-scoring experiment to run next (experiment
  prioritization).
- `channel-roi-ranking` — ROAS ranking across paid/organic channels, which to
  scale vs. cut (metric-driven budget decisions).

Verified locally in the worktree:
- `python3 scripts/agent_eval.py --role growth-marketer --tier sonnet --enforce`
  → `growth-marketer [sonnet]: accuracy=0.833 over 3 task(s) [PASS @>=0.80], cost=n/a (inert)`, exit 0.
- `python3 scripts/agent_eval.py --check-gaming` → `OK: no gameable golden tasks.`, exit 0
  (each verifier's degenerate/empty-submission credit is 0.0).
- `git diff --stat -- scripts/agent_eval.py docs/AGENT-ROSTER.md` → empty; neither
  file touched (per ticket instruction — roster update is DAS-1535's job).

Committed locally only (no push, no PR — hard local-only per dispatch).
Handing off to QA Lead for review: `status: todo` → `in_review`,
`assignee: qa-eng` → `qa-lead`.

### 2026-07-04 — QA Lead (GATE-4 review: REWORK)
origin: output_guardrail — review FAILED. Concerns:
  - key_not_leaked FAILS: all three task.md 'Required submission' example blocks reproduce the EXACT graded answer, including the load-bearing computed values that each carry 0.5 credit. funnel-stage-fix/task.md:29-30 leaks priority_stage=purchase + expected_lift=165; experiment-prioritization/task.md:29-30 leaks top_experiment=email_drip_campaign + rice_score=180.0; channel-roi-ranking/task.md:25-26 leaks scale_channel=content_seo + cut_channel=affiliate. An agent could score 1.0 by copying the example without doing the funnel/RICE/ROAS math the tasks exist to measure.
  - Each task.md also asserts 'The answer key lives only in verify.py' — a claim the same file contradicts by printing the answer.
  - Fix (small, specific): replace the worked-answer values in each task.md 'Required submission' block with placeholder tokens, mirroring qa-eng's own evals (<int>, <function name>). Offline score is unaffected (grading uses recorded submissions/), so re-run should stay green at 0.833.
  - Separate follow-up (non-blocking here): the merged product-analyst reference has a milder categorical-only version of the same leak; a guild-wide cleanup to placeholder examples is warranted.
Fix, then re-review (return to qa-lead).

### 2026-07-04 — QA Engineer (R-5 rework fix)
Surgical fix for the GATE-4 answer-key leak. In all three `task.md`
'Required submission' example blocks, replaced the worked (gradable) answer
values with non-answer schema placeholders, mirroring the style already used
in `evals/qa-eng/*/task.md` (`<int>`, `<function name>`):

- `funnel-stage-fix/task.md`: `"priority_stage": "purchase"` /
  `"expected_lift": 165` → `"priority_stage": "<stage-name>"` /
  `"expected_lift": <float>`.
- `experiment-prioritization/task.md`: `"top_experiment": "email_drip_campaign"` /
  `"rice_score": 180.0` → `"top_experiment": "<experiment-id>"` /
  `"rice_score": <float>`.
- `channel-roi-ranking/task.md`: `"scale_channel": "content_seo"` /
  `"cut_channel": "affiliate"` → `"scale_channel": "<channel-name>"` /
  `"cut_channel": "<channel-name>"`.

Did NOT touch `verify.py`, `fixtures/`, `submissions/`, `scripts/agent_eval.py`,
or `docs/AGENT-ROSTER.md` — `git status --porcelain` shows only the 3 `task.md`
files changed. The "answer key lives only in verify.py" claim in each task.md
is now true (grep confirms no literal answer values remain).

Re-verified locally in the worktree:
- `python3 scripts/agent_eval.py --role growth-marketer --tier sonnet --enforce`
  → `growth-marketer [sonnet]: accuracy=0.833 over 3 task(s) [PASS @>=0.80]`, exit 0
  (unchanged — offline grading uses recorded `submissions/`, unaffected by the
  task.md text edit).
- `python3 scripts/agent_eval.py --check-gaming` → `OK: no gameable golden tasks.`, exit 0.
- `grep -n "purchase\|165\|email_drip_campaign\|180.0\|content_seo\|affiliate" evals/growth-marketer/*/task.md`
  → no matches (leak eliminated).

Committed locally only (no push, no PR — hard local-only). Returning to QA Lead
for re-review: `status: in_progress` → `in_review`, `assignee: qa-eng` → `qa-lead`.

Non-blocking note carried over from QA Lead's review (not actioned here, out of
this ticket's scope): the merged product-analyst reference has a milder
categorical-only version of the same leak — a guild-wide placeholder cleanup
may be warranted as separate follow-up work.

### 2026-07-04 — QA Lead (GATE-4 re-review after rework)
Rework fix objectively re-verified: leak→placeholders; leak-grep clean (no literal answer in task.md); `agent_eval --role growth-marketer --enforce` PASS (accuracy=0.833); --check-gaming clean; empty→0.0. Approved → done.
