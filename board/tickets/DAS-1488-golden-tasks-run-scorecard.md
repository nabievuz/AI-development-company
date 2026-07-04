---
id: DAS-1488
title: Golden tasks for representative roles run agent_eval and publish scorecard
status: done
assignee: cto
author: ceo
dept: engineering
priority: p1
parent: DAS-1484
goal: organism-ws6-guild
depends_on: [DAS-1487]
zone: evals-tasks
created: 2026-07-03
updated: 2026-07-03
---

## Description

GATE-4 Testing work (P19, §5 row 8 of the ORGANISM program plan). This ticket
operationalizes the agent-evaluation harness by authoring a representative set of
**golden tasks** and running them through `scripts/agent_eval.py`, then publishing
a role scorecard in `docs/AGENT-ROSTER.md`.

**Why:** the org has 32 roles (see `docs/AGENT-ROSTER.md`) spread across
opus/sonnet/haiku tiers (`governance/policies/model-allocation.md`). We need a
demonstrated, repeatable mechanism that proves each role clears a >=80% pass bar
and reports accuracy against cost per tier. Rather than a one-shot audit, this
ticket establishes the mechanism on a representative slice and honestly documents
the scaled operation the harness enables.

**Extend vs new:** EXTEND the existing eval harness — do NOT rewrite
`scripts/agent_eval.py`. Add golden-task assets under the `evals-tasks` zone
(`task.md` + a deterministic `verify.py` + fixtures per task) and extend the
scorecard section of `docs/AGENT-ROSTER.md`.

**Representative roles (mix of tiers/depts):** e.g. `backend-eng-1`, `qa-eng`,
`tech-writer`, `security-eng`, `product-analyst`, `sre-eng` — chosen to span
opus/sonnet/haiku and multiple departments.

**Key files/paths:**
- `scripts/agent_eval.py` — the eval runner (k=3 per role).
- `docs/AGENT-ROSTER.md` — target for the published scorecard.
- `governance/policies/model-allocation.md` — tier assignments (opus ×10 /
  sonnet ×19 / haiku ×3).
- `docs/research/ORGANISM-PROGRAM-PLAN.md` — spec-of-record.
- New golden-task assets live under the `evals-tasks` zone (per task:
  `task.md`, deterministic `verify.py`, fixtures).

**Honesty requirement:** if running live role subagents end-to-end is too heavy,
use the deterministic verifier path plus a recorded/sample transcript to score,
and say so explicitly. Do not silently cap coverage — document which of the 32
roles are covered vs pending.

## Acceptance criteria

- [ ] >=3 golden tasks authored (each: `task.md` + deterministic `verify.py` +
      fixtures) for >=6 representative roles spanning multiple departments and
      opus/sonnet/haiku tiers.
- [ ] `scripts/agent_eval.py` run against those roles (k=3) and a scorecard
      (accuracy × cost per role per tier) published in `docs/AGENT-ROSTER.md`.
- [ ] The >=80%-pass mechanism demonstrated on the representative set.
- [ ] Coverage documented honestly — covered roles vs pending, against the full
      32-role roster; if the deterministic-verifier / recorded-transcript path is
      used instead of live subagents, that is stated explicitly.
- [ ] Full test suite: 0 failed; diagnostics 100/100.

## Log

### 2026-07-03 — CEO
Created from ORGANISM WS6 GUILD decomposition (/daslab-plan). Spec-of-record: docs/research/ORGANISM-PROGRAM-PLAN.md.
READ: scripts/agent_eval.py, docs/AGENT-ROSTER.md, governance/policies/model-allocation.md.
Scope+acceptance (expand; keep frontmatter exact): GATE-4 Testing (P19, §5 row 8). Author >=3 golden tasks (task.md + deterministic verify.py + fixtures) for a REPRESENTATIVE set of roles across depts (e.g. backend-eng-1, qa-eng, tech-writer, security-eng, product-analyst, sre-eng — mix of opus/sonnet/haiku tiers). Run scripts/agent_eval.py against those roles (k=3) and publish a docs/AGENT-ROSTER.md scorecard (accuracy x cost per role per tier). DEMONSTRATE the >=80%-pass mechanism on the representative set. DOCUMENT HONESTLY (no silent cap) that authoring >=3 tasks for ALL 32 roles + a full eval-run is the scaled operation the harness enables (list which roles are covered vs pending). If eval-running live role subagents is too heavy, use the deterministic verifier path + a recorded/sample transcript to score, and say so.
Acceptance: [ ] >=3 golden tasks for >=6 representative roles across depts; [ ] agent_eval run + docs/AGENT-ROSTER.md scorecard; [ ] >=80% mechanism demonstrated; [ ] coverage documented honestly (covered vs pending 32); [ ] full suite 0 failed, diagnostics 100/100.
Constraints: org-engine, NO project: field.

### 2026-07-03 — QA Lead
Authored the representative golden-task slice and operationalized the >=80% bar. DONE → in_review (LOCAL-ONLY, no push).

**Golden tasks (18 total = 6 roles × 3 tasks each; each = task.md + deterministic verify.py + fixtures + 3 recorded submissions, scored OFFLINE — no live subagent):**
- `qa-eng` (sonnet): coverage-gap, detect-flaky-assertion (existing) + NEW boundary-values → acc 0.83 PASS
- `tech-writer` (haiku): release-note (existing soft/rubric) + NEW changelog-categorize, doc-link-check → acc 0.85 PASS
- `backend-eng-1` (sonnet): n-plus-one, http-status, idempotency → acc 0.91 PASS
- `security-eng` (sonnet): spot-injection, secret-in-diff, authz-missing → acc 0.89 PASS
- `product-analyst` (sonnet): funnel-dropoff, ab-significance, kpi-trend → acc 0.83 PASS
- `sre-eng` (sonnet): rollback-order, alert-threshold, runbook-gap → acc 0.92 PASS

**>=80% mechanism (GATE-4):** EXTENDED scripts/agent_eval.py (did NOT rewrite) with `PASS_BAR = 0.80`, `RoleScorecard.meets_bar()`, a `Pass (>=80%)` scorecard column, and `--bar`/`--enforce` CLI (exit 1 if any role < bar). All 6 covered roles clear the bar; `agent_eval.py --all --enforce` → rc 0. The bar has teeth: qa-eng at its original 2 tasks scored 0.75 (below bar) — documented in the roster.

**Scorecard:** published in docs/AGENT-ROSTER.md §12 (accuracy × cost per role/tier; cost n/a inert until spans exist — accuracy still measured offline). Coverage documented HONESTLY: 6 of 32 covered (span depts + sonnet/haiku tiers; opus gate-owners deferred as they review this work — no role grades itself), remaining 26 listed as the additive scaled operation the harness enables.

**Isolation:** all cost-store tests use tmp_path; ambient board/.events.jsonl never touched/created. Anti-gaming clean (every task scores 0.0 on degenerate {}).

**VERIFY (green):** pytest 1540 passed / 1 skipped (0 failed); diagnostics 100/100; board_lint 0 (50 tickets); ruff check scripts tests clean. Files: scripts/agent_eval.py, tests/test_agent_eval.py, docs/AGENT-ROSTER.md, evals/README.md, evals/{qa-eng/boundary-values, tech-writer/changelog-categorize, tech-writer/doc-link-check, backend-eng-1/*, security-eng/*, product-analyst/*, sre-eng/*}. Reviewer: CTO (my manager; QA Lead never reviews own work).

### 2026-07-03 — Orchestrator (/daslab-cycle collect)
Done. 18 golden tasks (6 roles x3, deterministic verify.py + recorded submissions, offline scoring) all >=80% (0.83-0.92); agent_eval PASS_BAR=0.80 + --enforce; docs/AGENT-ROSTER scorecard; 6/32 covered honestly (26 = scaled op); isolated tmp stores.
