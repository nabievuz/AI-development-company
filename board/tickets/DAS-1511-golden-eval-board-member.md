---
id: DAS-1511
title: Golden eval — author 3 deterministic tasks for board-member (sonnet)
status: done
assignee: qa-lead
author: ceo
dept: engineering
priority: p1
parent: DAS-1508
goal: organism-ws6-guild
spec: 001-organism-eval-coverage
implements: [FR-001, FR-002]
zone: evals-board-member
created: 2026-07-04
updated: 2026-07-04
---

## Description

Author the golden-eval set for the **board-member** role (assigned tier: **sonnet**,
dept: governance) — part of R-5 (epic DAS-1508), raising coverage to 32/32.

Create **≥3** golden tasks under `evals/board-member/<task-id>/`, each exercising a
core competency of board-member per its overlay (`.claude/agents/board-member.md`) and its
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
`scripts/agent_eval.py --role board-member --enforce`.

**Extend, don't fork:** add assets only; do not modify `scripts/agent_eval.py`.
Do NOT edit `docs/AGENT-ROSTER.md` here — the roster scorecard is updated once,
in the synthesis ticket DAS-1535 (avoids a shared-zone merge conflict).

## Acceptance criteria
- [ ] `evals/board-member/` has ≥3 task dirs, each with `task.md` + `fixtures/` + deterministic `verify.py` + k=3 `submissions/`.
- [ ] `python3 scripts/agent_eval.py --role board-member --enforce` exits 0 at the sonnet tier (mean ≥0.80).
- [ ] `--check-gaming` clean for board-member; empty-submission → 0.0 verified.
- [ ] No change to `scripts/agent_eval.py` or `docs/AGENT-ROSTER.md`.

## Log
### 2026-07-04 — CEO
Created from goal decomposition (/daslab-plan) — R-5 role coverage (board-member).

### 2026-07-04 — QA Engineer
Authored 3 deterministic golden tasks under `evals/board-member/`, mirroring
`evals/README.md` + `evals/qa-eng/` shape exactly (task.md + fixtures/ +
verify.py + submissions/ k=3, answer key only in verify.py):

- `hire-vote-tally` — tallies agent-hire votes per the Governance Charter
  decision rule ("any single Board member may approve; only Board may
  reject"), ignoring non-Board votes.
- `charter-scope-classify` — classifies proposals against a dept charter's
  `authority` vs `out_of_scope` lists and resolves the correct escalation
  owner (governance oversight / charter-review competency).
- `adr-signoff-check` — checks a draft ADR against required sections and the
  Decision Rules' per-kind sign-off requirement (e.g. `strategy` needs BOTH
  chairman + board-member approved), reporting pass/fail + gaps (board-level
  sign-off / DoD "law-check captured" competency).

Verification run (all local, no live subagent dispatch):
```
$ python3 scripts/agent_eval.py --role board-member --tier sonnet --enforce
board-member [sonnet]: accuracy=1.000 over 3 task(s) [PASS @>=0.80], cost=n/a (inert)
EXIT:0

$ python3 scripts/agent_eval.py --check-gaming
OK: no gameable golden tasks.
EXIT:0
```
Also confirmed empty-submission ({}) → 0.0 credit individually for all 3 new
tasks via `degenerate_credit()`. Confirmed no diff to `scripts/agent_eval.py`
or `docs/AGENT-ROSTER.md` (`git status --porcelain` empty for both — the
roster scorecard update is left to synthesis ticket DAS-1535 per the ticket's
instruction).

Committed locally (no push — hard local-only per dispatch). Handing off to QA
Lead for review; `assignee` set to `qa-lead` per ROUTING.md, `status:
in_review`.

### 2026-07-04 — QA Lead (GATE-4 review)
Reviewed independently (adversarial). enforce PASS (accuracy=1), deterministic verifiers, empty→0.0, answer-key not leaked, tasks meaningful & distinct. Approved → done.
