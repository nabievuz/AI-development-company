---
id: DAS-1610
title: A2A Development — outbound endpoint reusing the 0009 admission and 0012 redaction edge
status: backlog
assignee: backend-eng-1
author: ceo
dept: engineering
priority: p1
parent: DAS-1606
goal: mustaqil-a2a-outbound
spec: 009-mustaqil-a2a-outbound
implements: [FR-001, FR-005]
labels: [security]
zone: tools/a2a
depends_on: [DAS-1608, DAS-1609]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 3 — Development (part A of GATE-3 for A2A OUTBOUND).**

Build the A2A outbound endpoint per the DAS-1608/DAS-1609 designs:

- Stand up the endpoint (out-of-process, mirrors the ADR-0033 governed-edge
  shape used elsewhere in MUSTAQIL) so that an external agent-system caller
  reaches "deliver this spec through the AADL-gated org" — governed delivery
  only, never raw tool/agent access (FR-001, extends ADR-0036 OB-1).
- Wire the endpoint through the existing ADR-0009 admission layer and ADR-0012
  redaction discipline at the boundary — reuse the same chain the ADR-0036
  outbound edge already uses; do NOT stand up a second, parallel admission path
  (FR-005).
- Wire the `a2a_outbound` feature flag (landed in DAS-1607) so the endpoint does
  not exist / is a no-op when the flag is OFF.
- Wire the in-tenant boundary check from DAS-1609's design so the endpoint
  refuses to resolve to, or be pointed at, a non-in-tenant address.

Fold in any on-branch prototype spike if one exists ahead of this ticket
(ADR-0020 — a spike is not a delivery until it passes in CI under a merged
ticket); if none exists, build fresh against the DAS-1608/DAS-1609 contracts.

## Acceptance criteria
- [ ] The A2A endpoint exists as an out-of-process governed surface; a call through it can only trigger AADL-gated delivery, never raw tool/agent access (FR-001).
- [ ] The endpoint routes every call through the existing ADR-0009 admission + ADR-0012 redaction chain; no second admission path exists (FR-005).
- [ ] With `a2a_outbound` OFF (default), the endpoint does not run / does not exist at dispatch time.
- [ ] The endpoint fails closed against a non-in-tenant target per the DAS-1609 boundary check.
- [ ] Merged PR, green CI; `diagnostics.py` 100/100; no `project:` field (R9).

## Log
### 2026-07-24 — Senior Product Manager
Created by `/daslab-plan` (A2A Development, endpoint half). Depends on both
Design children (DAS-1608, DAS-1609). Gated behind DAS-1606's binding sequencing
note (after WS-B, deferred until after WS-G's proof per Q12) — left in `status:
backlog` until that gate opens. Note for the implementing engineer: this ticket
requires the ADR-0034 headless runner (WS-B) to dispatch through — do not start
before WS-B's own epic is closed, regardless of this ticket's local dependency
graph (no WS-B id exists yet to encode that as `depends_on`).
