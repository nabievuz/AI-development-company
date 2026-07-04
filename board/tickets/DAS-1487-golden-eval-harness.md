---
id: DAS-1487
title: Golden-eval harness and agent_eval runner
status: done
assignee: cto
author: ceo
dept: engineering
priority: p1
parent: DAS-1484
goal: organism-ws6-guild
depends_on: [DAS-1485]
zone: evals-harness
produces: eval-harness
created: 2026-07-03
updated: 2026-07-03
---

## Description

Build a golden-eval harness that measures each agent role's real competence and cost, so the org can rank roles/models on evidence rather than reputation. This is GATE-3 (P19) of the ORGANISM WS6 GUILD program.

**What/why.** Today there is no role-level golden benchmark: quality checks (`scripts/check_t7_quality.py` + `config/t7_rubric.yaml`) score individual deliverables against a rubric, `scripts/check_metric_gaming.py` guards against metric gaming, and `scripts/cost/cost_ledger.py` records spend — but nothing ties a role's accuracy to its cost across a curated task set. This ticket adds that missing layer: a repeatable, mostly-deterministic benchmark per role that emits an accuracy×cost scorecard.

**Layout.** Golden tasks live under `evals/<role>/<task-id>/` with three parts:
- `task.md` — the task prompt/spec handed to the agent.
- `fixtures/` — any input files/state the task needs.
- `verify.py` — a DETERMINISTIC verifier returning fractional credit in `[0.0, 1.0]`.

**Runner.** `scripts/agent_eval.py` runs each task with `k=3` attempts, awards fractional credit per attempt, aggregates accuracy per role per model tier, and pairs it with cost pulled from `scripts/cost/cost_ledger.py`. Output is an accuracy×cost record per (role, model-tier).

**Verifier discipline.** Verifiers are deterministic wherever possible. A haiku-as-judge path is allowed ONLY for soft, rubric-scored tasks, and it MUST reuse the existing `config/t7_rubric.yaml` dimensions via `scripts/check_t7_quality.py` — do NOT fork or write a parallel scorer.

**Anti-gaming.** Inherit the discipline in `scripts/check_metric_gaming.py`: the eval score itself must not become a new gameable metric (no trivially-passable tasks, no leaking verifier internals into fixtures, no reward for empty/degenerate output).

**Downstream.** Results feed the scorecards in `docs/AGENT-ROSTER.md` and are consumed by DAS-1488.

**Extend vs new.** NEW runner (`scripts/agent_eval.py`) and NEW `evals/` tree. REUSE (do not fork): `scripts/check_t7_quality.py`, `config/t7_rubric.yaml`, `scripts/cost/cost_ledger.py`, `scripts/metrics_lib.py`, and the anti-gaming logic in `scripts/check_metric_gaming.py`.

**Key files/paths.**
- `scripts/agent_eval.py` (new runner)
- `evals/<role>/<task-id>/{task.md,fixtures/,verify.py}` (new golden-task tree + example tasks)
- `scripts/check_t7_quality.py`, `config/t7_rubric.yaml` (soft-task rubric — reuse)
- `scripts/cost/cost_ledger.py` (cost source)
- `scripts/metrics_lib.py`, `scripts/check_metric_gaming.py` (metrics + anti-gaming)
- `docs/AGENT-ROSTER.md` (scorecard sink)
- Spec-of-record: `docs/research/ORGANISM-PROGRAM-PLAN.md`

## Acceptance criteria

- [ ] `evals/<role>/<task-id>/{task.md, fixtures/, verify.py}` layout established.
- [ ] `scripts/agent_eval.py` runs `k=3` attempts with fractional credit and records accuracy×cost per role per model tier (cost from cost-ledger).
- [ ] Verifiers are deterministic; haiku-as-judge is used ONLY for soft rubric-scored tasks.
- [ ] Soft-task scoring reuses `config/t7_rubric.yaml` via `scripts/check_t7_quality.py` (no parallel scorer).
- [ ] Anti-gaming discipline from `scripts/check_metric_gaming.py` is inherited (evals not gameable).
- [ ] A couple of example golden tasks exist and the runner scores an example role deterministically.
- [ ] Results feed `docs/AGENT-ROSTER.md` scorecards.
- [ ] Full test suite: 0 failed; diagnostics 100/100.

## Log

### 2026-07-03 — CEO
Created from ORGANISM WS6 GUILD decomposition (/daslab-plan). Spec-of-record: docs/research/ORGANISM-PROGRAM-PLAN.md.
READ: scripts/check_t7_quality.py, config/t7_rubric.yaml, scripts/check_metric_gaming.py, scripts/cost/cost_ledger.py, scripts/metrics_lib.py.
Scope: GATE-3 (P19). Golden-eval harness — layout evals/<role>/<task-id>/{task.md, fixtures/, verify.py} + scripts/agent_eval.py runner (k=3, fractional credit, accuracy×cost per role per model tier from cost-ledger). Deterministic verifiers everywhere; haiku-as-judge ONLY for rubric-scored soft tasks (reuse config/t7_rubric.yaml dimensions, do not fork). Inherit check_metric_gaming anti-gaming discipline. Results feed docs/AGENT-ROSTER.md scorecards. Build harness + runner + a couple example golden tasks + tests (runner scores an example role deterministically).
Produces: eval-harness (consumed by DAS-1488).

### 2026-07-03 — QA Lead
Built the golden-eval harness (GATE-3 / P19).

Delivered:
- `scripts/agent_eval.py` — runner. k=3 attempts, fractional credit in [0,1], accuracy×cost per (role, model-tier). Cost pulled from `scripts/cost/cost_ledger.py` (`aggregate_spans`, no re-implemented parsing; inert→cost None). Deterministic verifiers via each task's `verify.py`; soft rubric tasks REUSE `config/t7_rubric.yaml` through `scripts/check_t7_quality.py` (`load_rubric`+`check_rubric_integrity`+`weighted_score`) — no parallel scorer. Anti-gaming inherited from `check_metric_gaming.py`: `gaming_findings` probes every task with a degenerate empty submission and fails any that scores >0 (`--check-gaming`; also gate-first before scoring).
- `evals/` (NEW tracked tree) + `evals/README.md` documenting the layout and the fixtures-vs-submissions anti-gaming boundary. Example golden tasks: `evals/qa-eng/detect-flaky-assertion` + `evals/qa-eng/coverage-gap` (deterministic) and `evals/tech-writer/release-note` (soft/rubric, haiku-as-judge). Recorded `submissions/` let the runner score a role end-to-end WITHOUT dispatching a live subagent: qa-eng scores accuracy 0.75 over 2 tasks; tech-writer 0.80.
- `governance/schemas/eval-harness.yaml` — typed-output contract (`produces: eval-harness`, consumed by DAS-1488); board_lint R11 validates it.
- `docs/AGENT-ROSTER.md` §12 — scorecard sink (accuracy×cost table + regenerate commands).
- `tests/test_agent_eval.py` — 25 tests (discovery, deterministic scoring, k honoured, rubric reuse == check_t7_quality.weighted_score, anti-gaming clean/flagged, cost from spans, scorecard render, CLI).
- Regenerated `.github/CODEOWNERS` for the new `/evals/` area (gen_codeowners.py).

VERIFY (FULL, green): `python3 -m pytest -q` → 1519 passed, 1 skipped, 0 failed; `python3 scripts/diagnostics.py` → 100/100; `python3 scripts/board_lint.py` → 0 violations; `ruff check scripts tests` → clean.

Committed LOCAL only (STRICT local-only; no push/PR). Status → in_review, assignee → cto (reviewer per board/ROUTING.md; qa-lead reports to CTO — not ceo).

### 2026-07-03 — Orchestrator (/daslab-cycle collect)
Done via local-only done-gate: full suite 1534 + diagnostics 100/100 + check_agents_sync green (combined-merge verified; cleared WS3-proof residue from board/.events.jsonl). agent_eval.py runner (k=3, fractional credit, accuracy x cost from cost_ledger) + evals/<role>/<task>/{task.md,fixtures,verify.py} layout + 3 example evals scored end-to-end from recorded submissions + governance/schemas/eval-harness.yaml + docs/AGENT-ROSTER.md scorecard + 25 tests. Reuses t7_rubric (no fork), inherits anti-gaming.
