---
id: DAS-1615
title: MUSTAQIL WS-F TEMPO — HEARTBEAT go-live EPIC
status: backlog
assignee: cto
author: ceo
dept: engineering
priority: p1
parent:
goal: mustaqil-ws-f-tempo
spec: 010-mustaqil-ws-f-tempo
labels: [governance, security]
depends_on: [DAS-1543]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**EPIC — MUSTAQIL v3.0 WS-F TEMPO. LAST workstream in the map, Founder-gated, only
after a ≥3-day clean shadow window.** Unlike WS-A…H, this is a **governance act, not
engineering**: HEARTBEAT (ORGANISM WS4, ADR-0027) is already built and shipped
**OFF** — `scripts/loop_controller.py`, `scripts/break_glass.py`,
`scripts/check_loop_mode.py`, `scripts/check_heartbeat_readiness.py`, and
`docs/runbooks/heartbeat-go-live.md` all exist, and the WS4 tickets that built them
(DAS-1472…1478, DAS-1538) are all `done`. WS-F's job is to **verify SI-1…SI-7
coverage, close any real gaps in the shadow/evidence tooling, and produce one
Founder-facing go/no-go artifact** — never to author a second scheduler or flip the
flag itself.

**Contract of record:** ADR-0027 (Accepted, SI-1…SI-7),
`docs/specs/010-mustaqil-ws-f-tempo/SPEC.md` (FR-001…FR-006, SC-001…SC-004), direction
brief row F ("F last, Founder-gated after a ≥3-day clean shadow window"), MUSTAQIL
BUDGET precondition (monthly Claude-subscription credit ceiling as an additional
outer cap alongside SI-5).

**Extend-vs-new (do not duplicate).** Reuse, verify, and where genuinely gapped,
extend: `scripts/loop_controller.py`, `scripts/break_glass.py`,
`scripts/check_heartbeat_readiness.py`, `scripts/metrics_history_feeder.py` (or
equivalent), `docs/runbooks/heartbeat-go-live.md`, and the kill-switch drill tests
from DAS-1478. Do not author a second readiness reporter, a second runbook, or a
second kill-switch mechanism.

**Sequencing note (informational, not a hard `depends_on`).** The MUSTAQIL v3.0
master prompt orders WS-F **last** — after A, B, C, D, E, G, H. As of this epic's
creation, only WS-A (DAS-1544…1551) has board tickets; WS-B…E/G/H have not yet been
planned onto the board, so this epic cannot `depends_on` ids that do not exist
(`check_dependency_graph` would flag a dangling ref). The **real** hard gate on
WS-F's Deployment child is not "other workstreams done" but **SI-7's own ≥3-day
clean shadow window + explicit Founder flag-flip** (FR-006) — that gate is enforced
inside DAS-1622, not by a cross-workstream `depends_on` chain. Whoever plans WS-B…H
onto the board should keep WS-F's Deployment child last to dispatch by convention,
not by a fabricated dependency edge.

**AADL — eight-child closure (children DAS-1616..1623, 2 Development + 2 Testing):**

| Child | Stage | Ticket | Owner-hint |
|---|---|---|---|
| DAS-1616 | Planning | Confirm ADR-0027 (Accepted) SI-1..SI-7 coverage + review SPEC-010 | cto |
| DAS-1617 | Design | Verification/evidence design — what "SI-N verified" means per invariant; runbook addenda (credit ceiling) | sre-lead |
| DAS-1618 | Development | Close real gaps in the shadow/evidence tooling (counted-wave feed, metrics history) | sre-eng |
| DAS-1619 | Development | Founder-facing go/no-go readiness report composing readiness + kill-switch + violation count | backend-em |
| DAS-1620 | Testing | SI-1..SI-7 verification drill — one enforcement point per invariant, all green | qa-eng |
| DAS-1621 | Testing | Kill-switch / break-glass drill — zero gate/approval violations in the event log | qa-eng |
| DAS-1622 | Deployment | **BLOCKED** — the `heartbeat_enabled` flip is Founder-only, after a ≥3-day clean shadow window | sre-lead |
| DAS-1623 | Maintenance | Recurring shadow-window/credit-ceiling health check feeding daslab-learn | product-analyst |

## Acceptance criteria
- [ ] All eight children (DAS-1616..DAS-1623) closed, each through its own AADL stage
      gate, EXCEPT DAS-1622 which correctly stays `blocked` pending the Founder act
      (that is its closure condition, per FR-006 — not a defect).
- [ ] **FR-001:** ADR-0027 confirmed as the sole binding contract; no duplicate
      scheduler/kill-switch/reporter authored.
- [ ] **FR-002/SC-001:** a fresh `check_heartbeat_readiness.py` run recorded verbatim
      (READY/NOT READY + exact clean-day count vs. the 3-day bar).
- [ ] **FR-003/SC-004:** `docs/runbooks/heartbeat-go-live.md` confirmed (or minimally
      extended) to separate the ≥3-day heartbeat clock from the ≥7-day loop-promotion
      clock and name the Founder-only flip step.
- [ ] **FR-004:** the monthly credit ceiling confirmed as an additional hard cap
      alongside SI-5 per-run/per-day caps in `config/budgets.yaml`.
- [ ] **FR-005/SC-002:** every SI-1..SI-7 invariant has a named, currently-passing
      enforcement artifact; the kill-switch/safety-rail drill shows zero violations.
- [ ] **FR-006:** no agent flips `heartbeat_enabled`; DAS-1622 stays `blocked` with the
      Founder-gate reason on record.
- [ ] `diagnostics.py` 100/100; `board_lint`/`check_spec_consistency`/
      `check_dependency_graph` green; no `project:` field on any WS-F ticket (R9).
- [ ] **Epic acceptance = AADL closure for WS-F, gated at Deployment on an explicit
      Founder act** — this is the intended terminal state, not an open defect.

## Log
### 2026-07-24 — Senior Product Manager
Created by /daslab-plan decomposition of MUSTAQIL v3.0 WS-F TEMPO (the LAST
workstream, Founder-gated). Contract = ADR-0027 (Accepted 2026-07-03, SI-1..SI-7) +
SPEC-010. Children DAS-1616..1623 (8: 1 Planning, 1 Design, 2 Development, 2 Testing,
1 Deployment [blocked-by-design], 1 Maintenance). Org-engine epic — no `project:`
field (board_lint R9). Depends on the MUSTAQIL program bootstrap (DAS-1543) for the
feature-flag/budget scaffold, same as WS-A. SPEC + tickets only — no dispatch, no
ADR authored, no code written, per this planning ticket's constraints.
