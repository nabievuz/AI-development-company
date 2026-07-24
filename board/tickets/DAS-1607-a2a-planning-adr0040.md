---
id: DAS-1607
title: A2A Planning — author ADR-0040, ratify, review SPEC-009, land the feature-flag decision
status: backlog
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
- [ ] ADR-0040 authored, Status `Proposed` → `Accepted` after CTO sign-off; explicitly framed as an extension of ADR-0036 (OB-1…OB-4 carried forward, A2A-specific goal-proposal-not-approval invariant added); Security Lead consult recorded; `docs/adr/README.md` updated with the new row.
- [ ] SPEC-009 reviewed (Status `reviewed`), no unresolved `[NEEDS CLARIFICATION]` markers.
- [ ] `a2a_outbound` feature key present in `config/features.yaml`, value `false`, with a consumer/flip comment in the existing style (mirrors `ws_a_tool_bridge`/`ws_d_langfuse_lens` comment shape); the reuse-vs-new decision is recorded in the ADR and this ticket's log.
- [ ] `check_spec_consistency`/`check_links`/`board_lint` green.

## Log
### 2026-07-24 — Senior Product Manager
Created by `/daslab-plan` (A2A Planning). Authors ADR-0040 (extends ADR-0036),
reviews SPEC-009, and decides the feature-flag question the dispatch contract
left open — recommendation carried in from the epic: a dedicated `a2a_outbound`
key, not a reuse of `ws_d_langfuse_lens`. Gated behind DAS-1606's binding
sequencing note (after WS-B, deferred until after WS-G's proof per Q12) — left
in `status: backlog`, not `todo`, until that gate opens.
