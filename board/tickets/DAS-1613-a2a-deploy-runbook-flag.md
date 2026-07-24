---
id: DAS-1613
title: A2A Deployment — runbook, flag stays OFF on merge, publish is a Founder act
status: backlog
assignee: sre-eng
author: ceo
dept: engineering
priority: p1
parent: DAS-1606
goal: mustaqil-a2a-outbound
spec: 009-mustaqil-a2a-outbound
implements: [FR-003, FR-006]
stage: GATE-5
labels: [security]
zone: docs/runbooks
depends_on: [DAS-1612]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 5 — Deployment (closes GATE-5 for A2A OUTBOUND).**

- Write the A2A outbound runbook: how the endpoint is deployed, how the
  `a2a_outbound` flag is checked, how to roll back (disable the flag / remove
  the endpoint wiring — no residual dispatch-behavior change).
- Confirm on merge: `a2a_outbound` stays OFF (FR-006) — this deployment does NOT
  flip it. The endpoint existing in the codebase, flag OFF, changes no dispatch
  or board behavior (byte-identical, SC-005).
- Document the **publish-is-a-Founder-act** procedure explicitly (FR-003): what
  a Founder does to flip `a2a_outbound` ON, what gets logged to
  `board/.events.jsonl`, and that this runbook step is never executed by an
  agent on its own initiative.
- Confirm the in-tenant boundary check (DAS-1609/DAS-1610) is wired into CI/
  diagnostics so a future misconfiguration toward a hosted relay fails closed.

## Acceptance criteria
- [ ] Runbook exists (`docs/runbooks/`) covering deploy, flag-check, and rollback for the A2A endpoint.
- [ ] `a2a_outbound` confirmed OFF at merge time; dispatch/board behavior byte-identical to pre-merge (SC-005).
- [ ] The publish-is-a-Founder-act procedure is documented, including the exact `board/.events.jsonl` log shape (FR-003).
- [ ] The in-tenant boundary check is wired into CI/diagnostics.
- [ ] Merged PR, green CI; `diagnostics.py` 100/100; `board_lint`/validators green; no `project:` field (R9).

## Log
### 2026-07-24 — Senior Product Manager
Created by `/daslab-plan` (A2A Deployment). Depends on DAS-1612 (Testing).
Gated behind DAS-1606's binding sequencing note (after WS-B, deferred until
after WS-G's proof per Q12) — left in `status: backlog` until that gate opens.
`stage: GATE-5` set per board convention for the deployment-stage child.
