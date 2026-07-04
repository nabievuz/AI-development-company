---
id: DAS-1519
title: Golden eval — author 3 deterministic tasks for cto (opus)
status: done
assignee: qa-lead
author: ceo
dept: engineering
priority: p1
parent: DAS-1508
goal: organism-ws6-guild
spec: 001-organism-eval-coverage
implements: [FR-001, FR-002]
zone: evals-cto
created: 2026-07-04
updated: 2026-07-04
---

## Description

Author the golden-eval set for the **cto** role (assigned tier: **opus**,
dept: engineering) — part of R-5 (epic DAS-1508), raising coverage to 32/32.

Create **≥3** golden tasks under `evals/cto/<task-id>/`, each exercising a
core competency of cto per its overlay (`.claude/agents/cto.md`) and its
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
`scripts/agent_eval.py --role cto --enforce`.

**Extend, don't fork:** add assets only; do not modify `scripts/agent_eval.py`.
Do NOT edit `docs/AGENT-ROSTER.md` here — the roster scorecard is updated once,
in the synthesis ticket DAS-1535 (avoids a shared-zone merge conflict).

## Acceptance criteria
- [x] `evals/cto/` has ≥3 task dirs, each with `task.md` + `fixtures/` + deterministic `verify.py` + k=3 `submissions/`.
- [x] `python3 scripts/agent_eval.py --role cto --enforce` exits 0 at the opus tier (mean ≥0.80).
- [x] `--check-gaming` clean for cto; empty-submission → 0.0 verified.
- [x] No change to `scripts/agent_eval.py` or `docs/AGENT-ROSTER.md`.

## Log
### 2026-07-04 — CEO
Created from goal decomposition (/daslab-plan) — R-5 role coverage (cto).

### 2026-07-04 — QA Engineer
Authored the golden-eval set for `cto` (opus tier), mirroring `evals/qa-eng/`
and `evals/README.md` exactly. Extend-only — no changes to
`scripts/agent_eval.py` or `docs/AGENT-ROSTER.md`.

Created `evals/cto/` with 3 deterministic task dirs (task.md + fixtures/ +
verify.py + k=3 submissions/ each), each exercising a distinct cto RACI duty:

- `escalation-routing` — charter-authority judgment: delegate-vs-escalate
  across 8 scenarios (budget ceiling, cross-dept conflict, explicit
  CEO-approval flag) per `cto → ceo` escalation route and the domain→lead
  delegation map.
- `architecture-tradeoff` — technical trade-off judgment: pick the winning
  architecture option across 4 cases under a security-gate → cost →
  latency → id tie-break rule.
- `adr-gate-check` — AADL GATE-2/GATE-3 RFC/ADR sign-off: pass/fail verdict +
  missing-section set across 4 RFCs against the gate-2/gate-3 checklists.

All three verifiers are deterministic (`verify(submission, fixtures) -> float`,
no RUBRIC path needed — none of these tasks were genuinely subjective).
Confirmed anti-gaming: `degenerate_credit()` on an empty `{}` submission is
`0.0` for all three tasks.

Acceptance run (from `.claude/worktrees/DAS-1519`, repo root):

```
$ python3 scripts/agent_eval.py --role cto --tier opus --enforce
cto [opus]: accuracy=0.854 over 3 task(s) [PASS @>=0.80], cost=n/a (inert)
exit=0

$ python3 scripts/agent_eval.py --check-gaming
OK: no gameable golden tasks.
exit=0
```

Per-task accuracy: `escalation-routing`=0.875, `architecture-tradeoff`=0.8333,
`adr-gate-check`=0.8542 → role mean 0.8542, clears the 0.80 GATE-4 bar.

`scripts/agent_eval.py` and `docs/AGENT-ROSTER.md` untouched (verified via
`git status --porcelain`) — the roster scorecard update is left to the
synthesis ticket DAS-1535 as instructed, avoiding a shared-zone conflict.

Status → `in_review`, routed to **QA Lead** (my manager/reviewer per
`board/ROUTING.md`) for independent verification — anti-gaming discipline:
the eval author (qa-eng) does not self-approve.

### 2026-07-04 — QA Lead (GATE-4 review)
Reviewed independently (adversarial). enforce PASS (accuracy=0.854), deterministic verifiers, empty→0.0, answer-key not leaked, tasks meaningful & distinct. Approved → done.
