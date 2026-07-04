---
id: DAS-1520
title: Golden eval — author 3 deterministic tasks for design-lead (sonnet)
status: done
assignee: qa-lead
author: ceo
dept: engineering
priority: p1
parent: DAS-1508
goal: organism-ws6-guild
spec: 001-organism-eval-coverage
implements: [FR-001, FR-002]
zone: evals-design-lead
created: 2026-07-04
updated: 2026-07-04
---

## Description

Author the golden-eval set for the **design-lead** role (assigned tier: **sonnet**,
dept: design) — part of R-5 (epic DAS-1508), raising coverage to 32/32.

Create **≥3** golden tasks under `evals/design-lead/<task-id>/`, each exercising a
core competency of design-lead per its overlay (`.claude/agents/design-lead.md`) and its
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
`scripts/agent_eval.py --role design-lead --enforce`.

**Extend, don't fork:** add assets only; do not modify `scripts/agent_eval.py`.
Do NOT edit `docs/AGENT-ROSTER.md` here — the roster scorecard is updated once,
in the synthesis ticket DAS-1535 (avoids a shared-zone merge conflict).

## Acceptance criteria
- [ ] `evals/design-lead/` has ≥3 task dirs, each with `task.md` + `fixtures/` + deterministic `verify.py` + k=3 `submissions/`.
- [ ] `python3 scripts/agent_eval.py --role design-lead --enforce` exits 0 at the sonnet tier (mean ≥0.80).
- [ ] `--check-gaming` clean for design-lead; empty-submission → 0.0 verified.
- [ ] No change to `scripts/agent_eval.py` or `docs/AGENT-ROSTER.md`.

## Log
### 2026-07-04 — CEO
Created from goal decomposition (/daslab-plan) — R-5 role coverage (design-lead).

### 2026-07-04 — QA Engineer
Authored `evals/design-lead/` with 3 deterministic golden tasks (mirroring
`evals/qa-eng/` and `evals/README.md` exactly — no new shape invented):

- `contrast-audit` — design review / accessibility gating: identify
  color-token pairs failing WCAG 2.1 AA normal-text contrast (`<4.5:1`),
  verified via the real relative-luminance/contrast-ratio formula computed
  independently in `verify.py` from `fixtures/tokens.json`.
- `spacing-grid-audit` — design-quality gating: identify spacing tokens that
  violate the design system's grid unit (`px % grid_base_px != 0`), derived
  from `fixtures/spacing-spec.json`.
- `variant-coverage-gap` — design-system governance: identify screen usages
  (`fixtures/screen-usage.json`) whose `component:variant` is undefined in the
  design-system registry (`fixtures/design-system.json`).

Each task: `task.md` + `fixtures/` (inputs only, no answer key) + deterministic
`verify.py` (set-based hits/false-positive credit, clamp01, empty→0.0) + `k=3`
recorded `submissions/attempt-{1,2,3}.json` (decreasing quality: perfect →
one/two omissions, no false positives — mirrors the qa-eng submission
pattern).

Verified locally (worktree `.claude/worktrees/DAS-1520`, branch
`feat/das-1520-golden-eval-design-lead`):
- `python3 scripts/agent_eval.py --role design-lead --tier sonnet --enforce`
  → `design-lead [sonnet]: accuracy=0.815 over 3 task(s) [PASS @>=0.80]`,
  exit 0.
- `python3 scripts/agent_eval.py --check-gaming` → `OK: no gameable golden
  tasks.`, exit 0 (covers empty-submission→0.0 for all 3 new tasks plus every
  other role's tasks).
- No changes to `scripts/agent_eval.py` or `docs/AGENT-ROSTER.md` (confirmed
  via `git status --porcelain`; only `evals/design-lead/` is new/untracked).

Status → `in_review`, reassigned to `qa-lead` per ROUTING.md (never review own
work). Committed locally only — no push, no PR (hard local-only directive).
No escalations; no blockers.

### 2026-07-04 — QA Lead (GATE-4 review)
Reviewed independently (adversarial). enforce PASS (accuracy=0.815), deterministic verifiers, empty→0.0, answer-key not leaked, tasks meaningful & distinct. Approved → done.
