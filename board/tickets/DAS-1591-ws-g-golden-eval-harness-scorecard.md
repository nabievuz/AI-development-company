---
id: DAS-1591
title: WS-G Development — golden-eval SWE-bench harness and run-scorecard
status: todo
assignee: backend-em
author: ceo
dept: engineering
priority: p1
parent: DAS-1588
goal: mustaqil-ws-g-proof
spec: 007-mustaqil-ws-g-proof
implements: [FR-003]
labels: [governance]
zone: evals
depends_on: [DAS-1590]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 3 — Development (closes GATE-3 for WS-G, part 1).** Build the golden-eval /
SWE-bench-style harness + run-scorecard per the DAS-1590 design.

- **FR-003:** a harness that scores a proof delivery against each ED-1 completion-contract
  dimension and emits the machine-readable run-scorecard. **Extend** the existing eval
  substrate (`scripts/agent_eval.py`, `evals/`, `evals/e2e/`) — do NOT stand up a
  parallel harness (extend-vs-new, ADR-0029).
- Include the **anti-gaming probe** so a delivery cannot be scored green without real
  artifacts; a dimension that cannot be measured is reported SKIPPED, never green (ADR-0020).
- **FR-007/TB flag:** guarded by `ws_g_proof` (OFF); with the flag OFF the harness/scorecard
  is inert and dispatch is byte-identical to pre-merge.
- Note the known pre-existing `evals/` ruff debt (~14 errors, flagged in the WS-A run) —
  bring touched files clean; do not let the harness inherit or spread it.

## Acceptance criteria
- [ ] Harness + run-scorecard extend `scripts/agent_eval.py` / `evals/` (not a parallel harness); emit the per-dimension machine-readable scorecard from DAS-1590.
- [ ] Anti-gaming probe present; unmeasured dimension → SKIPPED (never green).
- [ ] Guarded by `ws_g_proof` OFF; flag-off behaviour byte-identical to pre-merge.
- [ ] Touched files ruff-clean; `diagnostics.py` 100/100. Merged PR, green CI.

## Log
### 2026-07-24 — Senior Product Manager
Created by /daslab-plan (WS-G Development, part 1). FR-003 harness + run-scorecard,
extends the eval substrate; anti-gaming probe; behind `ws_g_proof` OFF.
</content>
