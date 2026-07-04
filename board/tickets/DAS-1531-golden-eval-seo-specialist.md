---
id: DAS-1531
title: Golden eval — author 3 deterministic tasks for seo-specialist (haiku)
status: done
assignee: qa-lead
author: ceo
dept: engineering
priority: p1
parent: DAS-1508
goal: organism-ws6-guild
spec: 001-organism-eval-coverage
implements: [FR-001, FR-002]
zone: evals-seo-specialist
created: 2026-07-04
updated: 2026-07-04
---

## Description

Author the golden-eval set for the **seo-specialist** role (assigned tier: **haiku**,
dept: marketing) — part of R-5 (epic DAS-1508), raising coverage to 32/32.

Create **≥3** golden tasks under `evals/seo-specialist/<task-id>/`, each exercising a
core competency of seo-specialist per its overlay (`.claude/agents/seo-specialist.md`) and its
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

The set MUST clear the ≥0.80 bar at the **haiku** tier when scored by
`scripts/agent_eval.py --role seo-specialist --enforce`.

**Extend, don't fork:** add assets only; do not modify `scripts/agent_eval.py`.
Do NOT edit `docs/AGENT-ROSTER.md` here — the roster scorecard is updated once,
in the synthesis ticket DAS-1535 (avoids a shared-zone merge conflict).

## Acceptance criteria
- [ ] `evals/seo-specialist/` has ≥3 task dirs, each with `task.md` + `fixtures/` + deterministic `verify.py` + k=3 `submissions/`.
- [ ] `python3 scripts/agent_eval.py --role seo-specialist --enforce` exits 0 at the haiku tier (mean ≥0.80).
- [ ] `--check-gaming` clean for seo-specialist; empty-submission → 0.0 verified.
- [ ] No change to `scripts/agent_eval.py` or `docs/AGENT-ROSTER.md`.

## Log
### 2026-07-04 — CEO
Created from goal decomposition (/daslab-plan) — R-5 role coverage (seo-specialist).

### 2026-07-04 — QA Engineer
Authored the seo-specialist golden-eval set at `evals/seo-specialist/` (mirrors
`evals/qa-eng/` + `evals/README.md` exactly — no harness changes):

- `title-meta-length-audit` — audits page `<title>`/meta-description lengths
  against standard SEO bounds (title 30–60 chars, meta 70–160 chars);
  precision/recall verifier over `fixtures/pages.json`.
- `structured-data-required-fields` — validates a `schema.org/Product`
  JSON-LD block for missing/empty required fields (`name`, `image`,
  `description`, `sku`, `offers.price`, `offers.priceCurrency`); verifier
  derives the invalid-field set from the fixture, not hardcoded.
- `broken-canonical-audit` — flags pages whose canonical tag is missing or
  points to a URL absent from the crawl (dangling canonical); verifier
  derives the broken-URL set from `fixtures/pages.json`.

Each task has `task.md` + `fixtures/` (inputs only, no answer key) +
deterministic `verify.py` (precision-recall style, matching
`evals/qa-eng/coverage-gap` and `boundary-values`) + k=3 recorded
`submissions/`. No `RUBRIC` soft path needed — all three are templated,
deterministic-friendly audits appropriate for the haiku tier.

Verified acceptance (all green, from the worktree):

```
$ python3 scripts/agent_eval.py --role seo-specialist --tier haiku --enforce
seo-specialist [haiku]: accuracy=0.852 over 3 task(s) [PASS @>=0.80], cost=n/a (inert)
EXIT:0

$ python3 scripts/agent_eval.py --check-gaming
OK: no gameable golden tasks.
EXIT:0
```

Confirmed empty-submission credit = 0.0 for all three tasks directly via
`degenerate_credit()`. Confirmed `git diff --stat` shows zero changes to
`scripts/agent_eval.py` or `docs/AGENT-ROSTER.md` — only new files under
`evals/seo-specialist/` were added (extend, don't fork).

Status → `in_review`, routed to QA Lead (my reviewer per role overlay /
ROUTING.md) for review + roster-scorecard follow-up (DAS-1535 owns the
`docs/AGENT-ROSTER.md` update, per this ticket's own instruction not to
touch it here).

Committed locally only (worktree `.claude/worktrees/DAS-1531`, branch
`feat/das-1531-golden-eval-seo-specialist`) — no push, no PR, per the
local-only directive.

### 2026-07-04 — QA Lead (GATE-4 review)
Reviewed independently (adversarial). enforce PASS (accuracy=0.852), deterministic verifiers, empty→0.0, answer-key not leaked, tasks meaningful & distinct. Approved → done.
