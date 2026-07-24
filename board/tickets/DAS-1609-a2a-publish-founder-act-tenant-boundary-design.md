---
id: DAS-1609
title: A2A Design — endpoint-publish-is-a-Founder-act and the in-tenant boundary
status: backlog
assignee: backend-em
author: ceo
dept: engineering
priority: p1
parent: DAS-1606
goal: mustaqil-a2a-outbound
spec: 009-mustaqil-a2a-outbound
implements: [FR-003, FR-004]
labels: [security]
zone: docs/design
depends_on: [DAS-1607]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 2 — Design (part B of GATE-2 for A2A OUTBOUND).**

Design the **publish and boundary contract** for the A2A endpoint:

- **Publish-is-a-Founder-act:** specify the concrete mechanism by which exposing
  the A2A endpoint beyond a disabled/internal state (or repointing it at any
  external registry/relay) requires an explicit, logged Founder action — extend
  the ADR-0036 OB-4 pattern (feature flag OFF by default; flipping ON / publishing
  is never automated or self-triggered by a workstream ticket) to the A2A surface
  specifically. Specify what gets logged to `board/.events.jsonl` and what the
  Founder-identity check looks like (mirrors ADR-0038 TN-3 — RBAC, not a chat
  string or a non-Founder actor).
- **In-tenant boundary (TN-1):** specify how the endpoint's reachability is
  constrained to the tenant boundary — no external/hosted A2A registry or relay
  may carry code/IP through this surface. Define the check (script/CI hook, or an
  addition to `scripts/check_in_tenant.py`'s `tenant_boundary.yaml` inventory)
  that fails a run if the A2A endpoint config resolves to a non-in-tenant address.
- State explicitly that this design reuses — does not replace — the ADR-0009
  admission layer and ADR-0012 redaction discipline; this ticket does not design
  a new admission mechanism, only the publish-gate and the boundary check.

No code in this stage — building the check and the endpoint wiring is DAS-1610's job.

## Acceptance criteria
- [ ] A written publish-gate design (or ADR-0040 addendum section) specifies the Founder-act mechanism, the `board/.events.jsonl` log shape, and the Founder-identity check (RBAC, mirrors TN-3).
- [ ] A written in-tenant boundary design specifies how the A2A endpoint is added to (or checked against) the TN-1 tenant-boundary inventory, and what a violation looks like.
- [ ] The design explicitly states no new admission/redaction mechanism is invented — ADR-0009/ADR-0012 are reused unmodified.
- [ ] `check_spec_consistency`/`check_links`/`board_lint` green; design ticket references SPEC-009 FR-003/FR-004 and ADR-0040.

## Log
### 2026-07-24 — Senior Product Manager
Created by `/daslab-plan` (A2A Design, publish + boundary half). Depends on
DAS-1607. Gated behind DAS-1606's binding sequencing note (after WS-B, deferred
until after WS-G's proof per Q12) — left in `status: backlog` until that gate opens.
