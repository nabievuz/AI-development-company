---
id: DAS-1553
title: WS-B Planning — ratify ADR-0034, review SPEC-003, carry the Q9 build-time marker
status: todo
assignee: cto
author: ceo
dept: engineering
priority: p1
parent: DAS-1552
goal: mustaqil-ws-b-runner
spec: 003-mustaqil-ws-b-runner
implements: [FR-001, FR-005]
labels: [governance, security]
zone: docs/adr
depends_on: [DAS-1544]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 1 — Planning (closes GATE-1 for WS-B).**

- Ratify **ADR-0034** (currently `Proposed`) → `Accepted` after CTO sign-off
  (RACI 3.1/3.6); Security Lead consulted on secrets/isolation (ADR-0034's own
  "second runtime surface to secure" accepted risk).
- Review `docs/specs/003-mustaqil-ws-b-runner/SPEC.md` (FR-001…FR-008,
  SC-001…SC-005); flip SPEC Status to `reviewed`.
- Carry forward, explicitly and without dropping it, the standing verification
  item:
  `[NEEDS CLARIFICATION: confirm the live Claude plan's Agent-SDK terms / per-plan
  credit / headless-use policy at build time — the 2026-06-15 credit model was
  announced then paused]`.
  This is NOT a blocker to ratifying ADR-0034 or reviewing SPEC-003 today — the
  master prompt already answered the model stance (Q9: subscription, account
  auth, monthly credit = ceiling). It IS a binding condition that MUST be
  re-verified before Deployment (DAS-1558) ever flips `ws_b_agent_sdk_runner`
  ON. Record it in this ticket's acceptance/log so it cannot be silently lost
  between now and that later, explicit Founder act.
- Confirm the WS-B feature key in `config/features.yaml` is present and
  `false` (already landed by DAS-1543 — confirm only, do not re-add or edit).

No code is built in this stage — this fixes the contract the WS-B Design and
Development tickets build against.

## Acceptance criteria
- [ ] ADR-0034 Status flipped to `Accepted` with the CTO sign-off recorded; `docs/adr/README.md` consistent.
- [ ] SPEC-003 reviewed (Status `reviewed`); FR-001…FR-008 / SC-001…SC-005 confirmed coherent, testable, and each traceable to an ADR-0034 SR invariant.
- [ ] The `[NEEDS CLARIFICATION: confirm the live Claude plan's Agent-SDK terms / per-plan credit / headless-use policy at build time — the 2026-06-15 credit model was announced then paused]` marker is recorded in this ticket as a standing pre-flip verification condition, explicitly handed to DAS-1558 (Deployment) — not silently dropped.
- [ ] WS-B feature key `ws_b_agent_sdk_runner` confirmed present and `false` in `config/features.yaml`.
- [ ] `check_spec_consistency`/`check_links`/`board_lint` green.

## Log
### 2026-07-24 — Senior PM
Created by `/daslab-plan` (WS-B Planning). Ratifies ADR-0034; reviews SPEC-003; the
Q9 credit-model caveat is carried as an explicit, non-blocking, must-re-verify-before-
flip condition rather than resolved here — the Founder already answered the model
stance in discovery Q9, but the live per-plan mechanics need a build-time check.
