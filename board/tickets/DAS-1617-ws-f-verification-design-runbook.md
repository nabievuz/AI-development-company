---
id: DAS-1617
title: WS-F Design — SI-1..SI-7 verification evidence design and go-live runbook addenda
status: todo
assignee: sre-lead
author: ceo
dept: engineering
priority: p1
parent: DAS-1615
goal: mustaqil-ws-f-tempo
spec: 010-mustaqil-ws-f-tempo
implements: [FR-003, FR-005]
labels: [governance, security]
zone: docs/design
depends_on: [DAS-1616]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 2 — Design (closes GATE-2 for WS-F).** Design what "SI-N is verified"
concretely means, and what (if anything) the existing go-live runbook still needs.
No new scheduler/kill-switch code — this is an evidence-mapping and documentation
design stage.

- **Evidence map (FR-005):** for each of SI-1…SI-7, name the exact existing
  enforcement artifact that proves it — e.g. SI-1 → `loop_controller.py`'s one-shot
  `--tick` contract + its tests; SI-2 → `scripts/check_loop_mode.py` exit-0;
  SI-3 → `scripts/break_glass.py` `is_active()` consult path; SI-4 → the quiet-hours
  config/tests; SI-5 → `config/budgets.yaml` + cost-ledger; SI-6 →
  `max_concurrent_waves = 1` enforcement; SI-7 → `check_heartbeat_readiness.py` +
  the never-auto-approve law. Flag any invariant with no currently-passing artifact
  as a **real gap** and hand it to DAS-1618/1619 — do not paper over one.
- **Runbook addenda (FR-003):** review `docs/runbooks/heartbeat-go-live.md` against
  SPEC-010; confirm it already separates the ≥3-day heartbeat clock from
  `loop_controller`'s ≥7-day loop-promotion clock and names the Founder-only flip.
  If MUSTAQIL's monthly-credit-ceiling precondition (Q9/FR-004) is not yet folded in,
  design the minimal addendum — extend the existing runbook, never fork a second one.
- Security Lead consulted on the never-auto-approve boundary (SI-7); SRE Lead
  accountable (owns the scheduler/runbook surface per DAS-1538 precedent).

## Acceptance criteria
- [ ] A design note (folded into this ticket or a short doc under `docs/design/`)
      maps each SI-1..SI-7 invariant to one named, currently-existing enforcement
      artifact — any gap explicitly flagged for DAS-1618/1619.
- [ ] `docs/runbooks/heartbeat-go-live.md` reviewed against SPEC-010 SC-004; confirmed
      compliant or a minimal, scoped addendum designed (credit ceiling / MUSTAQIL
      context) — no fork, no rewrite of the Founder-flip section.
- [ ] Security Lead review recorded on the SI-7 never-auto-approve boundary.
- [ ] `board_lint`/`check_spec_consistency` green.

## Log
### 2026-07-24 — Senior Product Manager
Created by /daslab-plan (WS-F Design). Maps SI-1..SI-7 to existing enforcement
artifacts; scopes the runbook addenda to the MUSTAQIL credit-ceiling precondition.
