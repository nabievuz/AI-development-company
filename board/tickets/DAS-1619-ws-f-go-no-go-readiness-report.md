---
id: DAS-1619
title: WS-F Development — Founder-facing go/no-go readiness report
status: todo
assignee: backend-em
author: ceo
dept: engineering
priority: p1
parent: DAS-1615
goal: mustaqil-ws-f-tempo
spec: 010-mustaqil-ws-f-tempo
implements: [FR-002, FR-004]
labels: [governance, security]
zone: scripts
depends_on: [DAS-1618]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 3 — Development (closes GATE-3 for WS-F, part 2).** Compose the
existing evidence sources into ONE Founder-facing go/no-go artifact — never a new
decision engine, never a shortcut around any existing check.

- Compose (do not reimplement): `scripts/check_heartbeat_readiness.py`'s verdict
  (clean-day streak vs. the ≥3-day bar), the kill-switch/safety-rail drill result
  (DAS-1478 / DAS-1621), and the never-auto-approve violation count from the event
  log (`check_never_auto_approve` / interrupt-card audit).
- Add the **monthly Claude-subscription credit ceiling** (FR-004) as an explicit line
  in the report: confirm it is documented in `config/budgets.yaml` as an outer cap
  alongside SI-5 per-run/per-day caps, and that credit exhaustion resolves to a
  sanctioned pause (idle + alert), not a false-green.
- Output: a single report (script output and/or a `docs/runbooks/` section) the
  Founder reads once before deciding whether to flip `heartbeat_enabled`. The report
  MUST state READY or NOT READY plainly and MUST NOT recommend or perform the flip —
  it is read-only evidence, never an approval.

## Acceptance criteria
- [ ] A single composed report exists (script and/or doc section) pulling from
      `check_heartbeat_readiness.py`, the kill-switch drill result, and the
      never-auto-approve violation count — no duplicate logic, only composition.
- [ ] The monthly credit ceiling appears in the report as a confirmed line item,
      cross-referenced to `config/budgets.yaml`'s `monthly_credit_ceiling`.
- [ ] The report is read-only: it states a verdict, never performs or recommends
      the flip; verified by inspection (no write path to `features.yaml` exists in
      the new code).
- [ ] `diagnostics.py` 100/100; merged PR, green CI where applicable.

## Log
### 2026-07-24 — Senior Product Manager
Created by /daslab-plan (WS-F Development, part 2). Composes existing evidence
sources (readiness reporter, kill-switch drill, violation count, credit ceiling)
into one Founder-facing go/no-go artifact — read-only, no flip capability.
