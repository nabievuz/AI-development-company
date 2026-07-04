---
id: DAS-1516
title: Golden eval — author 3 deterministic tasks for content-lead (sonnet)
status: done
assignee: qa-lead
author: ceo
dept: engineering
priority: p1
parent: DAS-1508
goal: organism-ws6-guild
spec: 001-organism-eval-coverage
implements: [FR-001, FR-002]
zone: evals-content-lead
created: 2026-07-04
updated: 2026-07-04
---

## Description

Author the golden-eval set for the **content-lead** role (assigned tier: **sonnet**,
dept: marketing) — part of R-5 (epic DAS-1508), raising coverage to 32/32.

Create **≥3** golden tasks under `evals/content-lead/<task-id>/`, each exercising a
core competency of content-lead per its overlay (`.claude/agents/content-lead.md`) and its
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
`scripts/agent_eval.py --role content-lead --enforce`.

**Extend, don't fork:** add assets only; do not modify `scripts/agent_eval.py`.
Do NOT edit `docs/AGENT-ROSTER.md` here — the roster scorecard is updated once,
in the synthesis ticket DAS-1535 (avoids a shared-zone merge conflict).

## Acceptance criteria
- [ ] `evals/content-lead/` has ≥3 task dirs, each with `task.md` + `fixtures/` + deterministic `verify.py` + k=3 `submissions/`.
- [ ] `python3 scripts/agent_eval.py --role content-lead --enforce` exits 0 at the sonnet tier (mean ≥0.80).
- [ ] `--check-gaming` clean for content-lead; empty-submission → 0.0 verified.
- [ ] No change to `scripts/agent_eval.py` or `docs/AGENT-ROSTER.md`.

## Log
### 2026-07-04 — CEO
Created from goal decomposition (/daslab-plan) — R-5 role coverage (content-lead).

### 2026-07-04 — QA Engineer
Authored 3 deterministic golden tasks under `evals/content-lead/` mirroring the
`evals/qa-eng/` template exactly (`task.md` + `fixtures/` + `verify.py` +
`submissions/` k=3):

- `style-guide-violations` — editorial-standards competency: detect banned
  corporate-jargon terms (from `fixtures/style_guide.json`) actually present in
  a draft blog post (`fixtures/draft.md`). Required set = {leverage, utilize,
  circle back, synergy}; scoring = (hits − false_positives) / |required|.
- `content-plan-priority` — content-plan prioritization competency: rank a
  5-item backlog (`fixtures/backlog.json`) by the formula
  `2*impact + 1.5*urgency − 1*effort`; scoring = fraction of concordant pairs
  vs. the submitted `order` (Kendall-style pairwise credit).
- `consistency-audit` — content-quality/consistency-check competency: flag
  which of 4 marketing snippets (`fixtures/docs/*.md`) deviate from the
  canonical product name/price in `fixtures/style_guide.json`. Required set =
  {doc-b.md, doc-c.md}; scoring = (hits − false_positives) / |required|.

All three verifiers are pure-Python, deterministic (no model call, no clock,
no randomness), and guard against a degenerate task (return 0.0 if the
required set would be empty). Answer keys live only in `verify.py`, never in
`fixtures/`.

Ran the full acceptance gate from the worktree
(`/Users/owner/DasLab/.claude/worktrees/DAS-1516`):

```
$ python3 scripts/agent_eval.py --role content-lead --tier sonnet --enforce
content-lead [sonnet]: accuracy=1.000 over 3 task(s) [PASS @>=0.80], cost=n/a (inert)
EXIT:0

$ python3 scripts/agent_eval.py --check-gaming
OK: no gameable golden tasks.
EXIT:0
```

Empty-submission probe (`agent_eval.degenerate_credit`) verified 0.0 for all
three new tasks: `style-guide-violations=0.0`, `content-plan-priority=0.0`,
`consistency-audit=0.0`.

Confirmed no diff to `scripts/agent_eval.py` or `docs/AGENT-ROSTER.md` — only
new files under `evals/content-lead/` were added (`git status --porcelain`
shows a single new untracked dir before commit).

Committed locally on branch `feat/das-1516-golden-eval-content-lead` in the
DAS-1516 worktree — **no push, no PR** (hard local-only per dispatch). Moving
to `in_review`, routed to `qa-lead` (per `board/ROUTING.md`, qa-eng's
reviewer) since I cannot review my own work.

### 2026-07-04 — QA Lead (GATE-4 review)
Reviewed independently (adversarial). enforce PASS (accuracy=1), deterministic verifiers, empty→0.0, answer-key not leaked, tasks meaningful & distinct. Approved → done.
