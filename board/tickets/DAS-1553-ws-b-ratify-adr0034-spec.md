---
id: DAS-1553
title: WS-B Planning — ratify ADR-0034, review SPEC-003, carry the Q9 build-time marker
status: done
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
- **RESOLVED (CTO, GATE-1): the live-terms question is a flip-time / Deployment
  precondition, NOT a build-time blocker.** The ADR-0034 runner is built and
  tested behind `ws_b_agent_sdk_runner` OFF regardless of the current live
  subscription terms — Founder discovery Q9 already fixed the model stance
  (subscription, Claude-account auth, monthly credit = the hard budget ceiling),
  which is all the Design and Development tickets need to build against. The
  live per-plan mechanics gate only turning the runner ON in production, not
  authoring it. This resolves the standing clarify-marker into a binding
  **DEPLOYMENT precondition bound to the WS-B Deployment ticket (DAS-1558)**:
  before `ws_b_agent_sdk_runner` is ever flipped ON, re-verify the current Claude
  plan's Agent-SDK terms / per-plan credit / headless-use policy against
  Anthropic's live documentation. It cannot be silently lost — it is recorded in
  this ticket's acceptance and closure log and explicitly handed to DAS-1558.
- Confirm the WS-B feature key in `config/features.yaml` is present and
  `false` (already landed by DAS-1543 — confirm only, do not re-add or edit).

No code is built in this stage — this fixes the contract the WS-B Design and
Development tickets build against.

## Acceptance criteria
- [x] ADR-0034 Status flipped to `Accepted` with the CTO sign-off recorded; `docs/adr/README.md` consistent.
- [x] SPEC-003 reviewed (Status `reviewed`); FR-001…FR-008 / SC-001…SC-005 confirmed coherent, testable, and each traceable to an ADR-0034 SR invariant.
- [x] The standing live-terms verification item is RESOLVED into a flip-time / Deployment precondition (not a build-time blocker) and explicitly handed to DAS-1558 (Deployment): before `ws_b_agent_sdk_runner` is flipped ON, re-verify the current Claude plan's Agent-SDK terms / per-plan credit / headless-use policy against Anthropic's live docs. Recorded here and in the closure log — not silently dropped.
- [x] WS-B feature key `ws_b_agent_sdk_runner` confirmed present and `false` in `config/features.yaml`.
- [x] `check_spec_consistency`/`check_links`/`board_lint` green.

## Log
### 2026-07-24 — Senior PM
Created by `/daslab-plan` (WS-B Planning). Ratifies ADR-0034; reviews SPEC-003; the
Q9 credit-model caveat is carried as an explicit, non-blocking, must-re-verify-before-
flip condition rather than resolved here — the Founder already answered the model
stance in discovery Q9, but the live per-plan mechanics need a build-time check.

### 2026-07-24 — CTO (GATE-1 closure)
**AADL Stage-1 (Planning) for WS-B RUNNER closed.** Three parts done, no defect found — not a rubber-stamp; each SR/FR/SC was traced.

1. **Clarify-marker resolved (not dropped).** The reviewer (me) resolved the two live-terms clarification points — confirming the current Claude Agent-SDK subscription terms and the headless-use / per-plan-credit policy (the 2026-06-15 credit model was announced then paused). Resolution: this is a **flip-time / Deployment precondition, NOT a build-time blocker**. The ADR-0034 runner is authored and tested behind `ws_b_agent_sdk_runner` OFF regardless of the live terms; Founder discovery Q9 already fixed the model stance (subscription, Claude-account auth, monthly credit = the hard budget ceiling), which is everything the WS-B Design/Development tickets build against. The live per-plan mechanics gate only turning the runner ON in production. The standing item is now bound as an explicit **DEPLOYMENT precondition on DAS-1558**: before `ws_b_agent_sdk_runner` is ever flipped ON, re-verify the current plan's Agent-SDK terms / per-plan credit / headless-use policy against Anthropic's live docs. No specific credit numbers invented. The literal `[NEEDS CLARIFICATION` marker prose was rewritten to resolved form so the ticket clears the ADR-0014 Definition-of-Ready gate (`check_clarifications.py --strict`).

2. **ADR-0034 ratified: Proposed → Accepted (CTO, 2026-07-24).** Verdict: SR-1…SR-5 sound. SR-2 makes the runner the ADR-0009 admission layer becoming a real in-orchestrator gateway (LAW 8 ceiling honored, not re-opened). SR-3 keeps the `run_wave(plan, results)` boundary — the runner makes no mechanical routing/selection/re-tier decision, so ADR-0025/0031 flag-on==flag-off holds at a function boundary (not a second producer). SR-1/SR-4 hold C1/C2: the generated `.claude/agents/*` shims stay canonical (no `create_agent` port), the board stays the source of truth, Git law intact, the runner never merges its own PR. SR-5 keeps it additive + flag-OFF (`/daslab-cycle` stays default). `docs/adr/README.md` row 0034 updated to Accepted / 2026-07-24.

3. **SPEC-003 reviewed: draft → reviewed.** FR-001…FR-008 / SC-001…SC-005 coherent, testable, each traced to an SR: FR-001→SR-1, FR-002→SR-2, FR-003→SR-3, FR-004→SR-4, FR-005→SR-5; FR-006/007/008 (subscription-account auth, budget/credit-breach = idle+alert / sanctioned pause, metered overflow OFF) trace to SR-2's admission-gateway + the ADR-0027 SI-5 budget ceiling grounded in Q9 — a WHAT-layer budget expansion, not a new HOW. SC-001↔SR-3/4, SC-002↔SR-2, SC-003↔SR-5, SC-004↔FR-007/008, SC-005 = release/lint bar. No dangling refs.

**Confirmed (not edited):** `config/features.yaml:21` carries `ws_b_agent_sdk_runner: false` (landed by DAS-1543).

**Validators (all exit 0):** `check_clarifications.py --strict`, `check_spec_consistency.py`, `check_links.py`, `board_lint.py`.

**Disposition:** LOCAL-ONLY (no git push/PR/commit) per dispatch. GATE-1 closed → **unblocks DAS-1554 (WS-B Design)**.
