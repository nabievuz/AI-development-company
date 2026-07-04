---
id: DAS-1538
title: R-4 prep — evidence-gated HEARTBEAT go-live readiness checker + Founder runbook
status: done
assignee: sre-lead
author: cto
dept: engineering
priority: p1
parent: DAS-1508
goal: organism-ws6-guild
zone: heartbeat-readiness
created: 2026-07-04
updated: 2026-07-04
---

## Description

Remediation **R-4** (HEARTBEAT loop shadow→live) is otherwise CODE-COMPLETE but is
blocked on Founder-only acts (QONUN-5 never-auto-approve): resolving push/CI so waves
are *counted*, accumulating a ≥3-day clean shadow window, and flipping
`heartbeat_enabled: true`. No agent may perform those. This ticket builds the
in-bounds part: the machinery that makes the eventual Founder flip **evidence-gated,
not vibes**.

**Deliverables:**

1. **`scripts/check_heartbeat_readiness.py`** — a read-only, evidence-gated reporter.
   It inspects the shadow window (`board/.metrics-history.jsonl`) and reports the
   ADR-0027 / §5-WS4 go-live bar criterion-by-criterion: `heartbeat_enabled` state +
   the consecutive clean-day streak (T1≥0.60, T2≤0.15, T7 holds) vs the 3-day
   minimum. It NEVER flips the flag and NEVER fabricates readiness (empty/short/unclean
   → NOT READY). Reuses `loop_controller.day_is_clean` / `clean_live_days` (no forked
   thresholds); the ladder-only T3/T4/T5 are neutralised so the window is exactly the
   WS4 T1/T2/T7 window. Exit 0 = READY, 1 = NOT READY. Deliberately NOT a blocking CI
   step (it is inert-red by design while the loop is off). +9 unit tests.
2. **`docs/runbooks/heartbeat-go-live.md`** — the Founder runbook: the precondition
   (push/CI so waves count), the ≥3-day shadow accumulation, the readiness check, the
   Founder-verified gates (kill-switch drill, zero violations), the flip itself, live
   monitoring, break-glass rollback, and the VERSION 2.0.0 release step.

## Acceptance criteria
- [x] `check_heartbeat_readiness.py` reports the go-live bar; honest NOT READY on the
      current (loop-off, empty-history) state; READY only on a real ≥3-day clean window.
- [x] Reuses loop_controller clean-day logic (no fork); +9 unit tests; ruff clean.
- [x] Founder runbook documents the safe, ordered, evidence-gated flip procedure.
- [x] `diagnostics.py` 100/100; full suite green.
- [ ] The actual `heartbeat_enabled: true` flip — FOUNDER-ONLY, out of scope (QONUN-5).

## Log
### 2026-07-04 — CTO
Built the R-4 go-live readiness gate (scripts/check_heartbeat_readiness.py, reusing
loop_controller.day_is_clean/clean_live_days with T3/T4/T5 neutralised to -inf so the
window is exactly WS4's T1/T2/T7 over ≥3 days) + Founder runbook
(docs/runbooks/heartbeat-go-live.md). Reporter is honest-inert: current state is
`heartbeat_enabled: false`, 0/3 clean days → NOT READY (exit 1), never fabricated.
+9 tests; ruff clean; diagnostics 100/100; full suite green. The flip itself stays
Founder-only (the one open acceptance box). This is the ceiling of R-4 progress
without a Founder decision on push/CI + the flip.
