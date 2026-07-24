---
id: DAS-1622
title: WS-F Deployment — HEARTBEAT go-live flip, Founder-only after a ≥3-day clean shadow window
status: blocked
assignee: sre-lead
author: ceo
dept: engineering
priority: p1
parent: DAS-1615
goal: mustaqil-ws-f-tempo
spec: 010-mustaqil-ws-f-tempo
implements: [FR-006]
stage: GATE-5
labels: [governance, security]
zone: docs/runbooks
depends_on: [DAS-1621]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 5 — Deployment (closes GATE-5 for WS-F).** This ticket is **blocked by
design** — its closure condition IS the Founder act, not something any agent
performs. Do not attempt to close it by flipping the flag.

- The `heartbeat_enabled: true` flip (ADR-0027 SI-7) is a **Founder-only,
  QONUN-5 never-auto-approve act**, gated on:
  1. A **≥3-day** rolling clean shadow window (`T1 ≥ 0.60 ∧ T2 ≤ 0.15 ∧ T7 holds`),
     confirmed by `scripts/check_heartbeat_readiness.py` — currently **0/3** (no
     counted-wave history yet; see DAS-1618).
  2. The DAS-1619 go/no-go report reading **READY**.
  3. The DAS-1620/1621 SI-1..SI-7 and kill-switch drills passing with **zero**
     gate/approval violations.
  4. An explicit Founder identity event (RBAC, not a chat string) performing the
     flip, per ADR-0038 TN-3 / QONUN-5.
- No agent may perform steps beyond confirming (1)–(3) are evidenced and presenting
  them. The flip itself, and the decision to opt into the launchd/cron entry (SI-1),
  are exclusively the Founder's.
- **Reason for `status: blocked`:** the Founder gate has not been triggered — the
  shadow window has not yet accumulated 3 clean days (0/3 as of ticket creation).
  This is an **external-dependency block** (`board/README.md` "blocked" rule) on a
  human act, not an agent stall.

## Acceptance criteria
- [ ] Evidence bundle assembled and linked (DAS-1619 go/no-go report, DAS-1620/1621
      drill results, `check_heartbeat_readiness.py` verdict) — ready for the Founder
      to review at any time.
- [ ] Runbook (`docs/runbooks/heartbeat-go-live.md`) confirmed current and reachable
      from this ticket.
- [ ] **This ticket stays `status: blocked` until the Founder performs the flip.**
      Closing it any other way (auto-approving, flipping the flag from an agent,
      or marking `done` without the Founder act) is a spec violation of FR-006.
- [ ] Only once the Founder has flipped `heartbeat_enabled: true` (and, if desired,
      opted into the OS scheduler entry) does this ticket move to `done`, with the
      Founder's act recorded in the log by whichever role observes/confirms it.

## Log
### 2026-07-24 — Senior Product Manager
Created by /daslab-plan (WS-F Deployment, GATE-5). Set `status: blocked` at creation
— this is intentional: the ticket's closure condition is an explicit Founder act
(the `heartbeat_enabled` flip after a ≥3-day clean shadow window, ADR-0027 SI-7),
which no agent may perform (QONUN-5). Blocked reason: the shadow window is currently
0/3 clean days (no counted-wave history yet, per `check_heartbeat_readiness.py`);
this is an external/human-gated block, not an agent stall — DAS-1618 addresses the
tooling gap that lets real days start accumulating once dispatch resumes. Nothing in
this workstream flips the flag; escalation is not applicable here — this is a
recorded, expected block, not a decision above charter authority.
