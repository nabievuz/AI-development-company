# DasLab — Golden-Eval Harness (`evals/`)

> **Audience: AI agents and operators.** This tree is the role-level golden
> benchmark that measures each agent role's real competence and cost, so the org
> can rank roles/models on **evidence** rather than reputation. It is GATE-3 (P19)
> of the ORGANISM WS6 GUILD program (DAS-1487). The runner is
> [`scripts/agent_eval.py`](../scripts/agent_eval.py).

## Why this exists

Before this harness, quality was measured only per-deliverable
([`scripts/check_t7_quality.py`](../scripts/check_t7_quality.py) +
[`config/t7_rubric.yaml`](../config/t7_rubric.yaml)), gaming was guarded by
[`scripts/check_metric_gaming.py`](../scripts/check_metric_gaming.py), and spend
was recorded by [`scripts/cost/cost_ledger.py`](../scripts/cost/cost_ledger.py) —
but nothing tied a **role's accuracy to its cost** across a curated task set.
This tree adds that missing layer: a repeatable, mostly-deterministic benchmark
per role that emits an accuracy×cost scorecard.

## Layout

```
evals/<role>/<task-id>/
    task.md          # the task prompt/spec handed to the agent
    fixtures/        # input files/state the task needs — given TO the agent
    verify.py        # a DETERMINISTIC verifier → fractional credit in [0.0, 1.0]
    submissions/     # recorded sample attempt(s) — the agent's OUTPUT, one JSON
                     # object per file, scored OFFLINE so a role can be graded
                     # end-to-end WITHOUT dispatching a live subagent.
```

`<role>` is a role key from [`board/ROUTING.md`](../board/ROUTING.md) (e.g.
`qa-eng`, `tech-writer`). `<task-id>` is a short slug.

### `fixtures/` vs `submissions/` — an anti-gaming boundary

This split is **load-bearing** (inherited from
[`check_metric_gaming.py`](../scripts/check_metric_gaming.py)'s Goodhart defence):

- `fixtures/` are **inputs the agent sees**.
- `submissions/` are **recorded outputs** — never shown to the agent.
- The **graded answer key lives ONLY in `verify.py`**. Putting the answer in
  `fixtures/` would leak verifier internals — **forbidden**.

## `verify.py` contract

A verifier exposes ONE of two paths:

1. **Deterministic (preferred, the default).**
   ```python
   def verify(submission: dict, fixtures: Path) -> float:
       """Return fractional credit in [0.0, 1.0]. Must be deterministic."""
   ```
   No model call, no clock, no randomness — the same submission always scores the
   same. An **empty/degenerate** submission MUST earn `0.0` (see anti-gaming).

2. **Soft, rubric-scored (haiku-as-judge — allowed ONLY here).**
   ```python
   RUBRIC = True
   ```
   The soft path REUSES the existing T7 rubric dimensions via
   [`check_t7_quality.py`](../scripts/check_t7_quality.py) (`load_rubric` +
   `check_rubric_integrity` + `weighted_score`) — it does **not** fork or
   re-implement a parallel scorer. Per-dimension scores come from a haiku judge at
   run time, or from the recorded submission's `judge_scores` field offline. A
   drifted rubric is refused, exactly as `check_t7_quality --scores` refuses it.

## Scoring

- Each task is scored over **`k` attempts** (default `k=3`); every attempt earns
  fractional credit in `[0.0, 1.0]`.
- Task accuracy = mean credit over attempts; role accuracy = mean over the role's
  tasks.
- Accuracy is paired with the role's estimated USD **cost** pulled from the DGO-X
  span ledger ([`cost_ledger.py`](../scripts/cost/cost_ledger.py)) to produce one
  **accuracy×cost** record per `(role, model-tier)`.
- **Inert-by-design:** when no spans exist yet (the loop-off baseline) the ledger
  returns `None`, so cost reports `n/a` while accuracy stays measurable offline.

## Anti-gaming (Goodhart defence)

The eval score must not become a new gameable metric. The runner probes every
task with a **degenerate empty submission** and FAILS the task if it earns any
credit (`agent_eval.py --check-gaming`). Rules of thumb when authoring a task:

- No trivially-passable tasks; a blank answer must score `0.0`.
- No leaking verifier internals into `fixtures/`.
- No reward for empty/degenerate output.

## Running

```bash
python3 scripts/agent_eval.py --role qa-eng --tier sonnet   # one role
python3 scripts/agent_eval.py --all --json                  # every role, JSON
python3 scripts/agent_eval.py --roster                      # scorecard markdown
python3 scripts/agent_eval.py --check-gaming                # anti-gaming probe only
```

Results feed the scorecards in [`docs/AGENT-ROSTER.md`](../docs/AGENT-ROSTER.md)
and are consumed downstream by DAS-1488.

## Tasks shipped in this tree

Representative coverage (DAS-1488): **6 roles × 3 golden tasks = 18 tasks**,
spanning departments and model tiers (sonnet ×5 + haiku ×1). All are scored
offline from recorded submissions — no live subagent dispatch. See
[`docs/AGENT-ROSTER.md` §12](../docs/AGENT-ROSTER.md) for the accuracy×cost
scorecard and the honest covered-vs-pending status against all 32 roles.

| Role | Tasks | Kind |
|---|---|---|
| `qa-eng` (sonnet) | `detect-flaky-assertion`, `coverage-gap`, `boundary-values` | deterministic |
| `tech-writer` (haiku) | `changelog-categorize`, `doc-link-check` | deterministic |
| `tech-writer` (haiku) | `release-note` | soft (rubric / haiku-as-judge) |
| `backend-eng-1` (sonnet) | `n-plus-one`, `http-status`, `idempotency` | deterministic |
| `security-eng` (sonnet) | `spot-injection`, `secret-in-diff`, `authz-missing` | deterministic |
| `product-analyst` (sonnet) | `funnel-dropoff`, `ab-significance`, `kpi-trend` | deterministic |
| `sre-eng` (sonnet) | `rollback-order`, `alert-threshold`, `runbook-gap` | deterministic |

The `--enforce` flag applies the 80% GATE-4 pass bar
(`agent_eval.py --all --enforce` exits non-zero if any role falls below it).
