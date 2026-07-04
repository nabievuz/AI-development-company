---
id: DAS-1524
title: Golden eval — author 3 deterministic tasks for frontend-eng-2 (sonnet)
status: done
assignee: qa-lead
author: ceo
dept: engineering
priority: p1
parent: DAS-1508
goal: organism-ws6-guild
spec: 001-organism-eval-coverage
implements: [FR-001, FR-002]
zone: evals-frontend-eng-2
created: 2026-07-04
updated: 2026-07-04
---

## Description

Author the golden-eval set for the **frontend-eng-2** role (assigned tier: **sonnet**,
dept: engineering) — part of R-5 (epic DAS-1508), raising coverage to 32/32.

Create **≥3** golden tasks under `evals/frontend-eng-2/<task-id>/`, each exercising a
core competency of frontend-eng-2 per its overlay (`.claude/agents/frontend-eng-2.md`) and its
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
`scripts/agent_eval.py --role frontend-eng-2 --enforce`.

**Extend, don't fork:** add assets only; do not modify `scripts/agent_eval.py`.
Do NOT edit `docs/AGENT-ROSTER.md` here — the roster scorecard is updated once,
in the synthesis ticket DAS-1535 (avoids a shared-zone merge conflict).

## Acceptance criteria
- [x] `evals/frontend-eng-2/` has ≥3 task dirs, each with `task.md` + `fixtures/` + deterministic `verify.py` + k=3 `submissions/`.
- [x] `python3 scripts/agent_eval.py --role frontend-eng-2 --enforce` exits 0 at the sonnet tier (mean ≥0.80).
- [x] `--check-gaming` clean for frontend-eng-2; empty-submission → 0.0 verified.
- [x] No change to `scripts/agent_eval.py` or `docs/AGENT-ROSTER.md`.

## Log
### 2026-07-04 — CEO
Created from goal decomposition (/daslab-plan) — R-5 role coverage (frontend-eng-2).

### 2026-07-04 — QA Engineer
Authored 3 deterministic golden tasks under `evals/frontend-eng-2/`, mirroring
`evals/README.md` + `evals/qa-eng/` shape exactly (task.md + fixtures/ +
verify.py + submissions/ k=3, no answer key leaked into fixtures/):

- `a11y-missing-labels` — accessibility correctness. `fixtures/form.html`
  (form with a labelled input, an unlabelled `email` input relying only on
  `placeholder`, a decorative-looking `avatar-img` missing `alt`, and an
  icon-only `icon-btn` with no accessible name). `verify.py` parses the real
  fixture markup to derive the violation set `{email, avatar-img, icon-btn}`
  (not hardcoded independent of the fixture); scores true-positive/false-positive
  set overlap, same formula as `evals/qa-eng/coverage-gap`.
- `render-null-crash` — UI rendering/edge-case bug. `fixtures/UserList.jsx`
  has an unguarded `users.map(...)` (line 4) that crashes when `users` is
  `undefined` before data loads. `verify.py` locates the buggy line by
  scanning the fixture source (not hardcoded) and checks `fix_kind` against
  an accepted null-safety strategy set; 0.5/0.5 split, mirrors
  `evals/qa-eng/detect-flaky-assertion`.
- `responsive-gap` — responsive-layout validation. `fixtures/styles.css`
  defines a sidebar+main layout with a `max-width:599px` mobile breakpoint
  and a `min-width:768px` desktop breakpoint, leaving an untargeted
  600-767px tablet gap that renders the desktop-tuned base rules too narrow
  (overlap bug). `verify.py` parses the actual breakpoints to derive the
  required gap range and scores submissions by intersection-over-union
  (clamped [0,1]) — penalises both misses and oversized/guessed ranges.

Verification run (worktree `.claude/worktrees/DAS-1524`, branch
`feat/das-1524-golden-eval-frontend-eng-2`):

```
$ python3 scripts/agent_eval.py --role frontend-eng-2 --tier sonnet --enforce
frontend-eng-2 [sonnet]: accuracy=1.000 over 3 task(s) [PASS @>=0.80], cost=n/a (inert)
EXIT=0

$ python3 scripts/agent_eval.py --check-gaming
OK: no gameable golden tasks.
EXIT=0
```

Also ran `python3 scripts/agent_eval.py --all --enforce` (exit 0) to confirm
no regression across the other roles' golden tasks. Confirmed via `git
status --short` that only `evals/frontend-eng-2/` is new — `scripts/agent_eval.py`
and `docs/AGENT-ROSTER.md` are untouched (roster scorecard update is deferred
to synthesis ticket DAS-1535 per the ticket's own instruction). Committed
locally only (no push, no PR — hard local-only per dispatch instructions).

Status → `in_review`, `assignee` → `qa-lead` (reviewer per ROUTING.md; never
self-review). Flagging for the orchestrator: DAS-1535 (roster synthesis) can
now pick up frontend-eng-2's 1.00 accuracy once this ticket is reviewed/merged.

### 2026-07-04 — QA Lead (GATE-4 review)
Reviewed independently (adversarial). enforce PASS (accuracy=1), deterministic verifiers, empty→0.0, answer-key not leaked, tasks meaningful & distinct. Approved → done.
