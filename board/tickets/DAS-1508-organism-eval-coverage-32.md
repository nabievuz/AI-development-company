---
id: DAS-1508
title: ORGANISM WS6/P19 — golden-eval coverage 6/32 → 32/32 (R-5)
status: done
assignee: qa-lead
author: ceo
dept: engineering
priority: p1
parent:
goal: organism-ws6-guild
spec: 001-organism-eval-coverage
created: 2026-07-04
updated: 2026-07-04
---

## Description

Remediation **R-5** of the ORGANISM v2.0 post-coding audit
(`docs/research/2026-07-03-organism-v2-verification.md`, finding F-6): the
golden-eval harness (WS6/P19, DAS-1487/1488) is real and green but covers only
**6 of 32 roles**. This epic raises coverage to **32/32** so §5 contract row 8
("all 32 roles ≥80% golden-eval at assigned tier") can be claimed on evidence.

**Extend, do NOT fork:** the harness contract is fixed by `evals/README.md`
(`task.md` + `fixtures/` + deterministic `verify.py` + recorded `submissions/`)
and the runner is `scripts/agent_eval.py`. Child tickets ADD assets under
`evals/<role>/`; nothing in the runner is rewritten.

**Anti-gaming ownership:** each role's eval is authored by an independent
evaluator (`qa-eng`), never by the role itself. The graded answer key lives ONLY
in `verify.py`; an empty/degenerate submission scores 0.0.

**Secondary purpose (R-4 linkage):** running these ~27 tickets as `/daslab-cycle`
waves emits real `run_start`/`run_end`/span events into the org event store —
the sustained shadow-window evidence that R-4 (HEARTBEAT go-live) is blocked on.

Spec: `docs/specs/001-organism-eval-coverage/SPEC.md`.

## Acceptance criteria
- [ ] All 26 remaining roles have ≥3 deterministic golden tasks (DAS-1509..1534 done).
- [ ] `scripts/agent_eval.py --enforce` exit 0 across all 32 roles; `--check-gaming` exit 0 (DAS-1535).
- [ ] `docs/AGENT-ROSTER.md` scorecard covers all 32 roles; any tier correction documented.
- [ ] `diagnostics.py` 100/100 and `board_lint.py` clean after the wave set closes.

## Log
### 2026-07-04 — CEO
Created from goal decomposition (/daslab-plan) — R-5 golden-eval coverage completion.

### 2026-07-04 — CEO (epic close)
All children done: DAS-1509..1534 (26 role golden-evals) + DAS-1535 (synthesis). Golden-eval coverage 6/32 → 32/32; agent_eval --all --enforce exit 0; §5 contract row 8 met. Epic → done.
