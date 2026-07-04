---
id: DAS-1534
title: Golden eval — author 3 deterministic tasks for ux-researcher (sonnet)
status: done
assignee: qa-lead
author: ceo
dept: engineering
priority: p1
parent: DAS-1508
goal: organism-ws6-guild
spec: 001-organism-eval-coverage
implements: [FR-001, FR-002]
zone: evals-ux-researcher
created: 2026-07-04
updated: 2026-07-04
---

## Description

Author the golden-eval set for the **ux-researcher** role (assigned tier: **sonnet**,
dept: design) — part of R-5 (epic DAS-1508), raising coverage to 32/32.

Create **≥3** golden tasks under `evals/ux-researcher/<task-id>/`, each exercising a
core competency of ux-researcher per its overlay (`.claude/agents/ux-researcher.md`) and its
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
`scripts/agent_eval.py --role ux-researcher --enforce`.

**Extend, don't fork:** add assets only; do not modify `scripts/agent_eval.py`.
Do NOT edit `docs/AGENT-ROSTER.md` here — the roster scorecard is updated once,
in the synthesis ticket DAS-1535 (avoids a shared-zone merge conflict).

## Acceptance criteria
- [ ] `evals/ux-researcher/` has ≥3 task dirs, each with `task.md` + `fixtures/` + deterministic `verify.py` + k=3 `submissions/`.
- [ ] `python3 scripts/agent_eval.py --role ux-researcher --enforce` exits 0 at the sonnet tier (mean ≥0.80).
- [ ] `--check-gaming` clean for ux-researcher; empty-submission → 0.0 verified.
- [ ] No change to `scripts/agent_eval.py` or `docs/AGENT-ROSTER.md`.

## Log
### 2026-07-04 — CEO
Created from goal decomposition (/daslab-plan) — R-5 role coverage (ux-researcher).

### 2026-07-04 — QA Engineer
Authored 3 deterministic golden tasks under `evals/ux-researcher/` mirroring the
`evals/qa-eng/` shape exactly (task.md + fixtures/ + verify.py + submissions/ k=3):

- `severity-triage` — applies a documented frequency×impact severity matrix
  (critical/major/minor) to 4 usability findings; credit = fraction of findings
  correctly triaged.
- `insight-vs-noise` — separates corroborated (≥2 participants) usability
  quotes from single-mention noise/anecdote quotes; credit = set-overlap
  (true positives minus false positives) over the true insight set.
- `theme-synthesis` — synthesizes per-session usability observations into
  themes and identifies the top theme by distinct-session coverage; credit =
  0.5 correct top theme + 0.5 correct session count.

All three answer keys are computed from their own fixture data inside
`verify.py` (never leaked into `fixtures/`), matching the qa-eng anti-gaming
discipline. Did not touch `scripts/agent_eval.py` or `docs/AGENT-ROSTER.md`.

Verification run (this worktree):
```
$ python3 scripts/agent_eval.py --role ux-researcher --tier sonnet --enforce
ux-researcher [sonnet]: accuracy=0.852 over 3 task(s) [PASS @>=0.80], cost=n/a (inert)
EXIT=0

$ python3 scripts/agent_eval.py --check-gaming
OK: no gameable golden tasks.
EXIT=0
```
Empty-submission probe is part of `--check-gaming` (`degenerate_credit`) and
passed for all 3 new tasks — confirmed clean.

Status → `in_review`, assignee → `qa-lead` (per ROUTING.md; never review own
work). Committed locally on branch `feat/das-1534-golden-eval-ux-researcher`;
no push/PR per the local-only directive.

### 2026-07-04 — QA Lead (GATE-4 review)
Reviewed independently (adversarial). enforce PASS (accuracy=0.852), deterministic verifiers, empty→0.0, answer-key not leaked, tasks meaningful & distinct. Approved → done.
