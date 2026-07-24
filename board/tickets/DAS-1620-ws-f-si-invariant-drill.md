---
id: DAS-1620
title: WS-F Testing — SI-1..SI-7 verification drill, one enforcement point per invariant
status: todo
assignee: qa-eng
author: ceo
dept: engineering
priority: p1
parent: DAS-1615
goal: mustaqil-ws-f-tempo
spec: 010-mustaqil-ws-f-tempo
implements: [FR-005]
labels: [governance, security]
zone: tests
depends_on: [DAS-1619]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 4 — Testing (closes GATE-4 for WS-F, part 1).** Run the SI-1…SI-7
verification drill against DAS-1617's evidence map: re-run every named enforcement
artifact and confirm it currently passes. This is verification, not new test
authorship, except where DAS-1618 added a fix that itself needs coverage.

- **SI-1** (one-shot `--tick`, no in-process timer) — confirm `loop_controller.py`'s
  dispatch contract and its existing tests pass.
- **SI-2** (`loop.yaml` stays shadow) — `scripts/check_loop_mode.py` exits 0.
- **SI-3** (break-glass honored) — covered by DAS-1621 (this ticket cross-references,
  does not duplicate).
- **SI-4** (quiet hours) — the quiet-hours config/tests pass; an unset config
  correctly means "no quiet window."
- **SI-5** (budget caps) — `config/budgets.yaml` caps enforced; a per-run/per-day
  breach evaluates to idle + alert (`scripts/check_cost.py` / `scripts/alerting.py`).
- **SI-6** (max-concurrent-waves = 1) — covered by DAS-1621 (cross-referenced).
- **SI-7** (never-auto-approve + ≥3-day shadow) — `check_heartbeat_readiness.py`
  reports honestly; `check_never_auto_approve` passes; gate/interrupt-card semantics
  hold (no auto-approval path exists).

## Acceptance criteria
- [ ] Every SI-1..SI-7 invariant has a re-run, currently-passing result recorded
      (test output or command transcript) in this ticket's log — no invariant
      asserted without a fresh run.
- [ ] Any invariant that fails is NOT waved through — it is logged as a defect and
      routed back to DAS-1618/1619, and this ticket does not close until re-verified.
- [ ] `diagnostics.py` 100/100; full relevant test suite green; merged PR if code
      changed, else a recorded local-run transcript.

## Log
### 2026-07-24 — Senior Product Manager
Created by /daslab-plan (WS-F Testing, part 1). Re-verifies each SI-1..SI-7
enforcement point named in DAS-1617's evidence map; SI-3/SI-6 cross-referenced to
the dedicated kill-switch drill (DAS-1621) to avoid duplicate test authorship.
