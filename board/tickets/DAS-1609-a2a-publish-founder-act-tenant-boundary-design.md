---
id: DAS-1609
title: A2A Design — endpoint-publish-is-a-Founder-act and the in-tenant boundary
status: done
assignee: cto
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
updated: 2026-07-25
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

### 2026-07-25 — Backend EM
Wrote the shared A2A OUTBOUND design doc `docs/design/a2a-outbound.md` covering
both design halves (one file avoids a same-`docs/design`-zone collision with
DAS-1608). **This ticket's scope is §2 (publish-is-a-Founder-act + in-tenant
boundary / A2-4, A2-6 / FR-003, FR-004):** the dedicated `a2a_outbound` flag OFF
by default (independent kill-switch, not a `ws_d_langfuse_lens` reuse); publishing
= a Founder act — authorized by a Founder-only `scripts/rbac.decide("a2a.publish")`
check (mirrors ADR-0038 TN-3, reuses the WS-E RBAC SSOT; RBAC not a chat string,
Founder identity from the session), logged to `board/.events.jsonl` as an
attributed+redacted `a2a_publish` event (shape specified), and deferred to the Q12
go-live gate; the in-tenant boundary via the **reused** `scripts/check_in_tenant.py`
+ a new `config/tenant_boundary.yaml` `a2a_outbound` entry (`carries_code_ip: true`,
role NOT in `accepted_external_roles`) — a hosted relay/registry config fails the
check (exit 1). Explicitly states ADR-0009 admission + ADR-0012 redaction are
**reused, not replaced** — one governed edge, no second admission path (no new
admission/redaction mechanism invented). §3 hands DAS-1612 the negative-path spec
for this half (SC-004 admission-skip + redaction probe; SC-003/SC-005 guard —
hosted-endpoint-blocked, flag-off inert, publish-requires-a-Founder-act).
Acceptance criteria met. Validators all exit 0: `board_lint.py` (0 violations),
`check_links.py` (no broken links), `check_spec_consistency.py` (10 SPECs OK).
LOCAL-ONLY — no commit/push/PR. Status → `in_review`, assignee → `cto` (GATE-2
accountable; Security Lead consulted). Touched only the design doc + this ticket.

### 2026-07-25 — CTO — GATE-2 CLOSURE (part B of two)
**GATE-2 (Design) CLOSED for the A2A publish + boundary half.** Reviewed §2 of
`docs/design/a2a-outbound.md` against Accepted ADR-0040 (A2-4/A2-5/A2-6), SPEC-009
FR-003/FR-004/FR-005, ADR-0038 TN-1/TN-3, ADR-0009 admission, ADR-0012 redaction,
ADR-0019 (flag OFF), and the reused WS-E RBAC SSOT (`scripts/rbac.py`). Carried the
Security-Lead consulted review myself.

Design ratified:
- **Publish is a Founder act.** Authorization is a Founder-only
  `scripts/rbac.decide("a2a.publish")` check (mirrors TN-3, reuses the WS-E RBAC
  SSOT) — Founder identity comes from the authenticated session, never from a chat
  string / ticket field / caller payload. Verified `rbac.py` already carries the
  structural double-lock (`FOUNDER_ONLY` + `load_grants()` refuse-to-load for a
  non-founder grant + `decide()` deny-by-default). Every publish/enable/repoint —
  allow and deny — is appended to canonical `board/.events.jsonl` (ADR-0024/0025,
  ADR-0012-redacted), and an `allow`+`principal_kind: founder` record is the only
  thing that marks the surface published (a bare flag-set is a forged claim).
  Deferred to the Q12 go-live gate; flag stays OFF on merge.
- **Flag OFF by default.** Dedicated `a2a_outbound: false` key confirmed present in
  `config/features.yaml` (NOT a `ws_d_langfuse_lens` reuse — an independent
  kill-switch). OFF ⇒ the endpoint does not exist, dispatch/board byte-identical to
  pre-merge (SC-005).
- **In-tenant only (TN-1).** Reuses the existing `scripts/check_in_tenant.py`
  (verified present) + one new `config/tenant_boundary.yaml` `a2a_outbound` entry
  (`carries_code_ip: true`, role deliberately NOT in `accepted_external_roles`) —
  a hosted-relay/registry config fails the check (exit 1). No public A2A SaaS
  surface (Q10).
- **One governed edge.** ADR-0009 admission + ADR-0012 redaction are explicitly
  reused, NOT replaced — A2A adds a caller *type*, not a second admission path. No
  new admission/redaction mechanism invented.

**Binding note for DAS-1610 (build):** to realize the *structural* refuse-to-load
lock the design invokes (not merely deny-by-default), the concrete `a2a.publish`
permission key MUST be registered in `rbac.py`'s `FOUNDER_ONLY` set alongside
`gate.approve`/`run.trigger`/`config.edit.security`. The exact key string is an
ADR-0040-sanctioned DAS-1610 choice; adding it to `FOUNDER_ONLY` is the mechanism,
not optional. Negative-path spec (§3: SC-004 admission-skip + redaction probe;
SC-003/SC-005 guard) accepted and handed to DAS-1612.
Validators exit 0: `board_lint.py` (0 violations), `check_links.py` (clean),
`check_spec_consistency.py` (10 SPECs OK). **Status → `done`. LOCAL-ONLY.**
Unblocks DAS-1610 (`tools/a2a` outbound endpoint).
