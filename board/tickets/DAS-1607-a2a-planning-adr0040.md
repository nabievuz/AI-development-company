---
id: DAS-1607
title: A2A Planning — author ADR-0040, ratify, review SPEC-009, land the feature-flag decision
status: done
assignee: cto
author: ceo
dept: engineering
priority: p1
parent: DAS-1606
goal: mustaqil-a2a-outbound
spec: 009-mustaqil-a2a-outbound
implements: [FR-001, FR-006]
labels: [security]
zone: docs/adr
depends_on: [DAS-1543]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 1 — Planning (closes GATE-1 for A2A OUTBOUND).**

**Do not dispatch before DAS-1606's binding gate opens** (after WS-B's epic lands
on the board, and only once WS-G's proof has demonstrably shipped per Q12).

- **Author ADR-0040** — "A2A outbound surface: DasLab as a callable governed agent"
  — as an explicit **extension** of ADR-0036 (OB-1…OB-4), not a fresh surface.
  Carry OB-1 (governed delivery, not raw agent access), OB-2's spirit (a system-
  of-record boundary — here: `board/.events.jsonl` + attestations stay canonical,
  an A2A caller's goal proposal is derived intake, never truth), OB-3 (admission +
  redaction at the boundary), and OB-4 (Founder-gated publishing) forward, adding
  the A2A-specific invariant that a caller's submission is a **goal proposal**,
  never a gate approval (QONUN-5). Draft as `Proposed`; CTO ratifies (RACI 3.1/3.6,
  same accountable owner as ADR-0036); Security Lead consulted (admission/redaction
  reuse, no second entry path).
- **Review SPEC-009** (`docs/specs/009-mustaqil-a2a-outbound/SPEC.md`, FR-001…FR-006,
  SC-001…SC-005); resolve any `[NEEDS CLARIFICATION]`; mark SPEC Status `reviewed`.
- **Land the feature-flag decision.** No dedicated A2A key exists in
  `config/features.yaml` yet. Decide and land: add a new `a2a_outbound` key
  (DEFAULT **OFF**, ADR-0019) rather than reusing `ws_d_langfuse_lens` — A2A is a
  distinct external-caller trust boundary and warrants its own independent
  kill-switch; coupling it to the WS-D observability lens flag would make the two
  surfaces un-independently-rollbackable. Record this decision explicitly in
  ADR-0040's Enforcement section and in this ticket's log.

No endpoint is built in this stage — this fixes the contract the A2A code builds against.

## Acceptance criteria
- [x] ADR-0040 authored, Status `Proposed` → `Accepted` after CTO sign-off; explicitly framed as an extension of ADR-0036 (OB-1…OB-4 carried forward, A2A-specific goal-proposal-not-approval invariant added); Security Lead consult recorded; `docs/adr/README.md` updated with the new row.
- [x] SPEC-009 reviewed (Status `reviewed`), no unresolved `[NEEDS CLARIFICATION]` markers.
- [x] `a2a_outbound` feature key present in `config/features.yaml`, value `false`, with a consumer/flip comment in the existing style (mirrors `ws_a_tool_bridge`/`ws_d_langfuse_lens` comment shape); the reuse-vs-new decision is recorded in the ADR and this ticket's log.
- [x] `check_spec_consistency`/`check_links`/`board_lint` green.

## Log
### 2026-07-24 — Senior Product Manager
Created by `/daslab-plan` (A2A Planning). Authors ADR-0040 (extends ADR-0036),
reviews SPEC-009, and decides the feature-flag question the dispatch contract
left open — recommendation carried in from the epic: a dedicated `a2a_outbound`
key, not a reuse of `ws_d_langfuse_lens`. Gated behind DAS-1606's binding
sequencing note (after WS-B, deferred until after WS-G's proof per Q12) — left
in `status: backlog`, not `todo`, until that gate opens.

### 2026-07-24 — CTO
**AADL Stage-1 (Planning) closed — GATE-1 for A2A OUTBOUND.**

- **ADR-0040 authored + ratified** (`docs/adr/0040-a2a-outbound-surface.md`, Status
  `Accepted`, dated CTO sign-off 2026-07-24). Framed explicitly as an **extension of
  ADR-0036** (OB-1…OB-4 carried forward), house style modelled on ADR-0033/0036. Six
  binding invariants: **A2-1** governed delivery, not raw agent access (extends OB-1);
  **A2-2** a caller's submission is a **goal PROPOSAL, never a gate approval** (QONUN-5
  — approvals stay Founder-only, the A2A-specific invariant, load-bearing); **A2-3**
  caller input is **untrusted** (injection defense, ADR-0033 TB-4 ingress — a proposal
  can never change goals/approvals/permissions); **A2-4** **in-tenant only** (ADR-0038
  TN-1, no external SaaS surface); **A2-5** same ADR-0009 admission + ADR-0012 redaction
  at the boundary, no second entry path (extends OB-3); **A2-6** dedicated `a2a_outbound`
  flag OFF, **publishing is a Founder act** (extends OB-4, ADR-0019). For this small
  governance ADR the CTO both authored and ratified (RACI 3.1/3.6, same accountable
  owner as ADR-0036), documenting the reasoning; Security Lead consult recorded
  (admission/redaction reuse, no second entry path). Added to `docs/adr/README.md`
  (table row + interop theme paragraph).
- **Q12 defer recorded as a Founder go-live gate** (not a build blocker): under the
  Founder "100% bajar" directive the A2A **machinery** is built now behind
  `a2a_outbound` **OFF**; **publishing a live endpoint is deferred until after the
  WS-G proof ships and is then a Founder act** (logged to `board/.events.jsonl`).
  Written into ADR-0040 Enforcement.
- **SPEC-009 reviewed** (`draft` → `reviewed`, 2026-07-24). FR-001…FR-006 / SC-001…SC-005
  checked coherent, testable, and traceable 1:1 to A2-1…A2-6; no `[NEEDS CLARIFICATION]`
  outstanding. (Review note deliberately avoids `FR-`/`SC-` id tokens so
  `check_spec_consistency` sees no duplicate ids.)
- **Feature-flag decision (landed):** added a **dedicated `a2a_outbound: false` key**
  to `config/features.yaml` — NOT a reuse of `ws_d_langfuse_lens`. Rationale (in ADR-0040
  Enforcement + here): A2A is a distinct external-caller trust boundary that must be
  enable/disable/rollback **independently** of the WS-D observability lens; one trust
  boundary, one kill-switch. Consumer/flip comment mirrors the existing WS-* style.
- **No defect found.** No invariant admits a path where an external caller could approve
  a gate (A2-2 + QONUN-5) or reach a non-in-tenant surface (A2-4 + TN-1); caller input is
  untrusted (A2-3). Nothing to route as a security defect.
- **Verify (all exit 0):** `check_spec_consistency` OK (10 SPECs), `check_links` OK,
  `board_lint` OK (180 tickets, 0 violations — the DAS-1507 body-status WARN is
  pre-existing and non-fatal).
- **Unblocks DAS-1608** (A2A Design). Touched only: `docs/adr/0040-a2a-outbound-surface.md`
  (new), `docs/adr/README.md`, `docs/specs/009-mustaqil-a2a-outbound/SPEC.md`,
  `config/features.yaml`, this ticket. LOCAL-ONLY — no push/PR/commit.
