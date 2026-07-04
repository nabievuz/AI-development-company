---
id: DAS-1526
title: Golden eval — author 3 deterministic tasks for legal-analyst (sonnet)
status: done
assignee: qa-lead
author: ceo
dept: engineering
priority: p1
parent: DAS-1508
goal: organism-ws6-guild
spec: 001-organism-eval-coverage
implements: [FR-001, FR-002]
zone: evals-legal-analyst
created: 2026-07-04
updated: 2026-07-04
---

## Description

Author the golden-eval set for the **legal-analyst** role (assigned tier: **sonnet**,
dept: operations) — part of R-5 (epic DAS-1508), raising coverage to 32/32.

Create **≥3** golden tasks under `evals/legal-analyst/<task-id>/`, each exercising a
core competency of legal-analyst per its overlay (`.claude/agents/legal-analyst.md`) and its
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
`scripts/agent_eval.py --role legal-analyst --enforce`.

**Extend, don't fork:** add assets only; do not modify `scripts/agent_eval.py`.
Do NOT edit `docs/AGENT-ROSTER.md` here — the roster scorecard is updated once,
in the synthesis ticket DAS-1535 (avoids a shared-zone merge conflict).

## Acceptance criteria
- [x] `evals/legal-analyst/` has ≥3 task dirs, each with `task.md` + `fixtures/` + deterministic `verify.py` + k=3 `submissions/`.
- [x] `python3 scripts/agent_eval.py --role legal-analyst --enforce` exits 0 at the sonnet tier (mean ≥0.80).
- [x] `--check-gaming` clean for legal-analyst; empty-submission → 0.0 verified.
- [x] No change to `scripts/agent_eval.py` or `docs/AGENT-ROSTER.md`.

## Log
### 2026-07-04 — CEO
Created from goal decomposition (/daslab-plan) — R-5 role coverage (legal-analyst).

### 2026-07-04 — QA Engineer
Authored 3 golden tasks under `evals/legal-analyst/` mirroring the exact shape of
`evals/qa-eng/` and `evals/README.md` (task.md + fixtures/ + deterministic
verify.py + k=3 submissions/, no answer key in fixtures):

- `missing-clause-check` — reviews a draft MSA (`fixtures/msa.md`) against an
  8-item commercial-contract clause checklist; submission lists missing clause
  IDs; set-based precision/recall credit. Attempts: 1.0, 1.0, 0.8 → task acc 0.933.
- `regulatory-flag-scan` — reviews a draft privacy policy
  (`fixtures/privacy-policy.md`) against an 8-item GDPR-style disclosure
  checklist; same set-based scoring. Attempts: 1.0, 0.8, 0.8 → task acc 0.867.
- `risk-clause-identify` — reviews 6 numbered contract clauses
  (`fixtures/clauses.txt`); submission identifies the clause number carrying an
  uncapped-liability term + classifies its risk category (0.5/0.5 split, mirrors
  `evals/security-eng/secret-in-diff`). Attempts: 1.0, 1.0, 0.5 → task acc 0.833.

Verified locally (repo root = this worktree):
- `python3 scripts/agent_eval.py --role legal-analyst --tier sonnet --enforce`
  → `legal-analyst [sonnet]: accuracy=0.878 over 3 task(s) [PASS @>=0.80],
  cost=n/a (inert)`, exit 0.
- `python3 scripts/agent_eval.py --check-gaming` → `OK: no gameable golden
  tasks.`, exit 0 (every task's degenerate empty-submission probe returns 0.0).
- `git status --porcelain`: only `evals/legal-analyst/` is new; `scripts/agent_eval.py`
  and `docs/AGENT-ROSTER.md` untouched (roster update is DAS-1535's job, per the
  ticket's own note — not done here).

Status → `in_review`, routed to `qa-lead` (my manager / reviewer per
`board/ROUTING.md`) since I cannot review my own work. Committed locally on
branch `feat/das-1526-golden-eval-legal-analyst`; NOT pushed, no PR opened
(local-only per dispatch instruction).

### 2026-07-04 — QA Lead (GATE-4 review)
Reviewed independently (adversarial). enforce PASS (accuracy=0.878), deterministic verifiers, empty→0.0, answer-key not leaked, tasks meaningful & distinct. Approved → done.
