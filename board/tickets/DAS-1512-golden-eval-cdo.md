---
id: DAS-1512
title: Golden eval — author 3 deterministic tasks for cdo (sonnet)
status: done
assignee: qa-lead
author: ceo
dept: engineering
priority: p1
parent: DAS-1508
goal: organism-ws6-guild
spec: 001-organism-eval-coverage
implements: [FR-001, FR-002]
zone: evals-cdo
created: 2026-07-04
updated: 2026-07-04
---

## Description

Author the golden-eval set for the **cdo** role (assigned tier: **sonnet**,
dept: design) — part of R-5 (epic DAS-1508), raising coverage to 32/32.

Create **≥3** golden tasks under `evals/cdo/<task-id>/`, each exercising a
core competency of cdo per its overlay (`.claude/agents/cdo.md`) and its
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
`scripts/agent_eval.py --role cdo --enforce`.

**Extend, don't fork:** add assets only; do not modify `scripts/agent_eval.py`.
Do NOT edit `docs/AGENT-ROSTER.md` here — the roster scorecard is updated once,
in the synthesis ticket DAS-1535 (avoids a shared-zone merge conflict).

## Acceptance criteria
- [x] `evals/cdo/` has ≥3 task dirs, each with `task.md` + `fixtures/` + deterministic `verify.py` + k=3 `submissions/`.
- [x] `python3 scripts/agent_eval.py --role cdo --enforce` exits 0 at the sonnet tier (mean ≥0.80).
- [x] `--check-gaming` clean for cdo; empty-submission → 0.0 verified.
- [x] No change to `scripts/agent_eval.py` or `docs/AGENT-ROSTER.md`.

## Log
### 2026-07-04 — CEO
Created from goal decomposition (/daslab-plan) — R-5 role coverage (cdo).

### 2026-07-04 — QA Engineer
Authored 3 deterministic golden tasks under `evals/cdo/` as the INDEPENDENT
eval author (anti-gaming: cdo does not author its own eval), mirroring the
`evals/qa-eng/` template exactly:

- `raw-hex-audit` — design-token governance (CDO Authority: "final word on
  tokens, components, and visual language"). Detect components whose fill
  bypasses the token system with a raw hex value.
- `contrast-gate` — accessibility baseline enforcement (CDO Authority: "block
  any release that violates accessibility baseline (WCAG AA)"). Apply the
  4.5:1 normal / 3.0:1 large WCAG AA thresholds to flag failing colour pairs.
- `duplicate-primitives` — design-system coverage (CDO Success Metric:
  "design system covers ≥90% of UI primitives"). Detect components that
  duplicate an existing UI purpose and are consolidation candidates.

Each task: `task.md` (prompt), `fixtures/*.json` (inputs only, no answer key),
`verify.py` (deterministic set-based precision/recall credit, answer key
derived from the fixture inside the verifier — never leaked), and 3 recorded
`submissions/attempt-{1,2,3}.json` (offline-graded, no live subagent
dispatch).

Verified acceptance (commands run from `evals/../` root):

```
$ python3 scripts/agent_eval.py --role cdo --tier sonnet --enforce
cdo [sonnet]: accuracy=0.904 over 3 task(s) [PASS @>=0.80], cost=n/a (inert)
EXIT=0

$ python3 scripts/agent_eval.py --check-gaming
OK: no gameable golden tasks.
EXIT=0
```

Degenerate (empty `{}`) submission credit confirmed `0.0` for all three tasks
(`raw-hex-audit`, `contrast-gate`, `duplicate-primitives`) via
`agent_eval.degenerate_credit`.

Confirmed no diff to `scripts/agent_eval.py` or `docs/AGENT-ROSTER.md`
(extend-only, per ticket instruction — roster synthesis is DAS-1535's job).

Status → `in_review`, reassigned to `qa-lead` per routing (never review own
work). Nothing to escalate; no other role's input needed.

### 2026-07-04 — QA Lead (GATE-4 review)
Reviewed independently (adversarial). enforce PASS (accuracy=0.904), deterministic verifiers, empty→0.0, answer-key not leaked, tasks meaningful & distinct. Approved → done.
