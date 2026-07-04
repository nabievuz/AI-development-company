---
id: DAS-1533
title: Golden eval — author 3 deterministic tasks for support-lead (haiku)
status: done
assignee: qa-lead
author: ceo
dept: engineering
priority: p1
parent: DAS-1508
goal: organism-ws6-guild
spec: 001-organism-eval-coverage
implements: [FR-001, FR-002]
zone: evals-support-lead
created: 2026-07-04
updated: 2026-07-04
---

## Description

Author the golden-eval set for the **support-lead** role (assigned tier: **haiku**,
dept: operations) — part of R-5 (epic DAS-1508), raising coverage to 32/32.

Create **≥3** golden tasks under `evals/support-lead/<task-id>/`, each exercising a
core competency of support-lead per its overlay (`.claude/agents/support-lead.md`) and its
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
`scripts/agent_eval.py --role support-lead --enforce`.

**Extend, don't fork:** add assets only; do not modify `scripts/agent_eval.py`.
Do NOT edit `docs/AGENT-ROSTER.md` here — the roster scorecard is updated once,
in the synthesis ticket DAS-1535 (avoids a shared-zone merge conflict).

## Acceptance criteria
- [x] `evals/support-lead/` has ≥3 task dirs, each with `task.md` + `fixtures/` + deterministic `verify.py` + k=3 `submissions/`.
- [x] `python3 scripts/agent_eval.py --role support-lead --enforce` exits 0 at the haiku tier (mean ≥0.80).
- [x] `--check-gaming` clean for support-lead; empty-submission → 0.0 verified.
- [x] No change to `scripts/agent_eval.py` or `docs/AGENT-ROSTER.md`.

## Log
### 2026-07-04 — CEO
Created from goal decomposition (/daslab-plan) — R-5 role coverage (support-lead).

### 2026-07-04 — QA Engineer
Authored 3 deterministic golden tasks under `evals/support-lead/`, mirroring
`evals/README.md` and the `evals/qa-eng/` shape exactly (task.md + fixtures/ +
verify.py + submissions/, k=3 each):

- `ticket-triage-routing` — triage rubric (category/route/priority) over 5
  tickets; credit = correct_fields / 15.
- `sla-breach-check` — first-response SLA breach decision from a fixed `now`
  + per-priority hour limits over 6 tickets; credit = correct_booleans / 6.
- `canned-response-match` — template-catalog matching over 5 customer
  messages; credit = correct_matches / 5.

All three verifiers are pure-deterministic (no clock/model calls; `now` in
`sla-breach-check` is a fixed fixture value, not wall-clock). Answer keys live
only in `verify.py`, never in `fixtures/`.

Acceptance evidence (run from `/Users/owner/DasLab/.claude/worktrees/DAS-1533`):

```
$ python3 scripts/agent_eval.py --role support-lead --tier haiku --enforce
support-lead [haiku]: accuracy=0.952 over 3 task(s) [PASS @>=0.80], cost=n/a (inert)
EXIT: 0

$ python3 scripts/agent_eval.py --check-gaming
OK: no gameable golden tasks.
EXIT: 0
```

Empty-submission (`{}`) verified to score `0.0` on all three tasks (this is
exactly what `--check-gaming` probes; it passed clean).

No changes to `scripts/agent_eval.py` or `docs/AGENT-ROSTER.md` — `git status`
shows only the new `evals/support-lead/` tree added. Set `status: in_review`,
`assignee: qa-lead` (reviewer per role overlay / ROUTING.md) for review —
not self-reviewing my own eval-authoring work.

### 2026-07-04 — QA Lead (GATE-4 review)
Reviewed independently (adversarial). enforce PASS (accuracy=0.952), deterministic verifiers, empty→0.0, answer-key not leaked, tasks meaningful & distinct. Approved → done.
