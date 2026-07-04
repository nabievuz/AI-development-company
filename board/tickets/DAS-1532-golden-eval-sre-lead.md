---
id: DAS-1532
title: Golden eval — author 3 deterministic tasks for sre-lead (opus)
status: done
assignee: qa-lead
author: ceo
dept: engineering
priority: p1
parent: DAS-1508
goal: organism-ws6-guild
spec: 001-organism-eval-coverage
implements: [FR-001, FR-002]
zone: evals-sre-lead
created: 2026-07-04
updated: 2026-07-04
---

## Description

Author the golden-eval set for the **sre-lead** role (assigned tier: **opus**,
dept: engineering) — part of R-5 (epic DAS-1508), raising coverage to 32/32.

Create **≥3** golden tasks under `evals/sre-lead/<task-id>/`, each exercising a
core competency of sre-lead per its overlay (`.claude/agents/sre-lead.md`) and its
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
`scripts/agent_eval.py --role sre-lead --enforce`.

**Extend, don't fork:** add assets only; do not modify `scripts/agent_eval.py`.
Do NOT edit `docs/AGENT-ROSTER.md` here — the roster scorecard is updated once,
in the synthesis ticket DAS-1535 (avoids a shared-zone merge conflict).

## Acceptance criteria
- [ ] `evals/sre-lead/` has ≥3 task dirs, each with `task.md` + `fixtures/` + deterministic `verify.py` + k=3 `submissions/`.
- [ ] `python3 scripts/agent_eval.py --role sre-lead --enforce` exits 0 at the opus tier (mean ≥0.80).
- [ ] `--check-gaming` clean for sre-lead; empty-submission → 0.0 verified.
- [ ] No change to `scripts/agent_eval.py` or `docs/AGENT-ROSTER.md`.

## Log
### 2026-07-04 — CEO
Created from goal decomposition (/daslab-plan) — R-5 role coverage (sre-lead).

### 2026-07-04 — QA Engineer
Authored the golden-eval set for `sre-lead` under `evals/sre-lead/` (3 deterministic
tasks, mirroring `evals/qa-eng/` + `evals/sre-eng/` shape exactly; no changes to
`scripts/agent_eval.py` or `docs/AGENT-ROSTER.md`):

- `incident-severity-triage` — apply a top-down SEV1..SEV4 policy (data-loss /
  revenue-impact / error-rate thresholds) across 5 concurrent incidents.
- `rollback-go-nogo` — reliability trade-off: ROLLBACK vs FORWARD_FIX vs MONITOR
  across 5 deployments, incl. the irreversible-migration vs data-loss-risk
  precedence case.
- `oncall-escalation-order` — triage/priority ordering of 5 concurrent incidents
  by severity → customer tier → age.

Each task has `task.md` + `fixtures/` (inputs only, no answer key) + a
deterministic `verify.py` (fractional credit, empty submission → 0.0) +
`submissions/` with k=3 recorded attempts (varied correctness, not all-perfect).

Verification run from the worktree:
- `python3 scripts/agent_eval.py --role sre-lead --tier opus --enforce` →
  `sre-lead [opus]: accuracy=0.844 over 3 task(s) [PASS @>=0.80], cost=n/a (inert)`,
  exit 0.
- `python3 scripts/agent_eval.py --check-gaming` → `OK: no gameable golden tasks.`,
  exit 0 (probed across the whole `evals/` tree, sre-lead included).
- Confirmed all three verifiers score an empty `{}` submission `0.0`
  (`incident-severity-triage 0.0`, `oncall-escalation-order 0.0`,
  `rollback-go-nogo 0.0`).
- `git status --porcelain` shows only `evals/sre-lead/` as new — no change to
  `scripts/agent_eval.py` or `docs/AGENT-ROSTER.md`.

Status → `in_review`, routed to QA Lead per ROUTING.md (never review own work).
No escalation needed; no additional cross-role work discovered. Committed
locally on branch `feat/das-1532-golden-eval-sre-lead` — NOT pushed, no PR
opened (local-only per dispatch instructions).

### 2026-07-04 — QA Lead (GATE-4 review)
Reviewed independently (adversarial). enforce PASS (accuracy=0.844), deterministic verifiers, empty→0.0, answer-key not leaked, tasks meaningful & distinct. Approved → done.
