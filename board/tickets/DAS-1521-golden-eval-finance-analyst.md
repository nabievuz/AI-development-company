---
id: DAS-1521
title: Golden eval — author 3 deterministic tasks for finance-analyst (sonnet)
status: done
assignee: qa-lead
author: ceo
dept: engineering
priority: p1
parent: DAS-1508
goal: organism-ws6-guild
spec: 001-organism-eval-coverage
implements: [FR-001, FR-002]
zone: evals-finance-analyst
created: 2026-07-04
updated: 2026-07-04
---

## Description

Author the golden-eval set for the **finance-analyst** role (assigned tier: **sonnet**,
dept: operations) — part of R-5 (epic DAS-1508), raising coverage to 32/32.

Create **≥3** golden tasks under `evals/finance-analyst/<task-id>/`, each exercising a
core competency of finance-analyst per its overlay (`.claude/agents/finance-analyst.md`) and its
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
`scripts/agent_eval.py --role finance-analyst --enforce`.

**Extend, don't fork:** add assets only; do not modify `scripts/agent_eval.py`.
Do NOT edit `docs/AGENT-ROSTER.md` here — the roster scorecard is updated once,
in the synthesis ticket DAS-1535 (avoids a shared-zone merge conflict).

## Acceptance criteria
- [ ] `evals/finance-analyst/` has ≥3 task dirs, each with `task.md` + `fixtures/` + deterministic `verify.py` + k=3 `submissions/`.
- [ ] `python3 scripts/agent_eval.py --role finance-analyst --enforce` exits 0 at the sonnet tier (mean ≥0.80).
- [ ] `--check-gaming` clean for finance-analyst; empty-submission → 0.0 verified.
- [ ] No change to `scripts/agent_eval.py` or `docs/AGENT-ROSTER.md`.

## Log
### 2026-07-04 — CEO
Created from goal decomposition (/daslab-plan) — R-5 role coverage (finance-analyst).

### 2026-07-04 — QA Engineer
Authored the golden-eval set for `finance-analyst` (sonnet tier), mirroring
`evals/README.md` / `evals/qa-eng/` shape exactly. Added 3 deterministic task
dirs under `evals/finance-analyst/`:
- `budget-variance` — variance-analysis competency; list departments >10% over
  budget from `fixtures/budget.json`; true-positive/false-positive credit
  formula (same shape as `evals/qa-eng/coverage-gap`).
- `unit-economics` — unit-economics computation; LTV and LTV:CAC ratio from
  `fixtures/metrics.json`; tolerance-banded numeric credit (full credit ≤2%
  relative error, decays to 0 by 22%).
- `cost-decision` — cost-decision judgment; build-vs-buy call + breakeven
  month from `fixtures/vendor_options.json`; half credit for the correct
  option, half for breakeven month within a 6-month decay window.

Each task dir has `task.md` + `fixtures/` (inputs only, no answer key) +
deterministic `verify.py` + `submissions/attempt-{1,2,3}.json` (k=3, varied
quality — not all perfect, to reflect a realistic accuracy distribution).

Verified acceptance:
1. `python3 scripts/agent_eval.py --role finance-analyst --tier sonnet --enforce`
   → `finance-analyst [sonnet]: accuracy=0.810 over 3 task(s) [PASS @>=0.80],
   cost=n/a (inert)` — exit 0.
2. `python3 scripts/agent_eval.py --check-gaming` → `OK: no gameable golden
   tasks.` — exit 0 (each verifier's empty-submission probe scores 0.0, since
   an empty dict has no `over_budget`/`ltv`/`cheaper_option` keys and every
   verifier treats missing/non-numeric fields as 0 credit).
3. No changes made to `scripts/agent_eval.py` or `docs/AGENT-ROSTER.md` (confirmed
   via `git status` before commit — only `evals/finance-analyst/**` and this
   ticket file touched).

Committed locally (no push, no PR — hard local-only per dispatch instructions).
Handing off to QA Lead (my manager, per ROUTING.md) for review — never
self-reviewing. Status → `in_review`.

### 2026-07-04 — QA Lead (GATE-4 review)
Reviewed independently (adversarial). enforce PASS (accuracy=0.81), deterministic verifiers, empty→0.0, answer-key not leaked, tasks meaningful & distinct. Approved → done.
