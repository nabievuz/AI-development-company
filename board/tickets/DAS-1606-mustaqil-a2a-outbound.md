---
id: DAS-1606
title: MUSTAQIL A2A OUTBOUND — DasLab as a callable governed agent, extending ADR-0036 (EPIC)
status: backlog
assignee: cto
author: ceo
dept: engineering
priority: p1
parent:
goal: mustaqil-a2a-outbound
spec: 009-mustaqil-a2a-outbound
labels: [security]
depends_on: [DAS-1543]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**EPIC — MUSTAQIL v3.0 A2A OUTBOUND (interop extension, rides the workstream map,
does not add a 9th workstream).** Extend the ADR-0036 outbound interop surface so
DasLab is also reachable as a **callable governed agent for another agent system**
(A2A). Governance rides along exactly as it does for the existing outbound surface:
an external caller can submit a **goal proposal**, never a gate approval (approvals
stay Founder-only, QONUN-5); **publishing an endpoint is a Founder act**; the surface
is **in-tenant only** (ADR-0038 TN-1). No new brain, no new admission path — A2A
reuses the ADR-0009 admission layer and ADR-0012 redaction discipline already
enforced at the ADR-0036 edge.

**Contract of record:** ADR-0040 (to be authored by this epic's Planning child,
extending ADR-0036 OB-1…OB-4), `docs/specs/009-mustaqil-a2a-outbound/SPEC.md`
(FR-001…FR-006, SC-001…SC-005), master prompt Part 1 interop-extension note +
Part 2, discovery answer Q12.

**Sequencing (binding — do not dispatch out of order):**
- **After WS-B** (needs the ADR-0034 headless runner the A2A endpoint dispatches
  through) — no WS-B epic ticket exists on the board yet, so this is a textual
  gate, not a `depends_on` edge (no id to point at without creating a dangling
  ref); re-check before dispatching any child below WS-B's epic.
- **Alongside WS-D** (both ride the ADR-0036/0033 edges; neither blocks the other).
- **DEFERRED until AFTER the WS-G proof lands (Q12 — Founder default: "defer A2A
  until after proof; build it as the first post-proof reach increment").** This
  epic and its children are created now (planning artifact, per this dispatch),
  but **none of DAS-1607..DAS-1614 should be actively worked until WS-G's proof
  is demonstrably shipped** — status `backlog` on every child reflects this,
  not merely "not yet started." The orchestrator/CEO must re-open this gate
  explicitly once WS-G lands; this ticket does not self-authorize that move.

**AADL — six-stage closure (children DAS-1607..DAS-1614, Design and Development
each split into two per the bracketed sub-items in the dispatch contract):**

| Child | Stage | Ticket | Owner-hint |
|---|---|---|---|
| DAS-1607 | Planning | Author ADR-0040, ratify, review SPEC-009, land the `a2a_outbound` feature-flag decision | cto |
| DAS-1608 | Design | Goal-proposal intake contract — never a gate approval | backend-em |
| DAS-1609 | Design | Endpoint-publish-is-a-Founder-act + the in-tenant boundary | backend-em |
| DAS-1610 | Development | A2A outbound endpoint, reusing the 0009 admission + 0012 redaction edge | backend-eng-1 |
| DAS-1611 | Development | Goal-proposal to board intake, never an approval | backend-eng-1 |
| DAS-1612 | Testing | Negative tests — gate-bypass, self-approval, admission-skip, redaction probe | qa-eng |
| DAS-1613 | Deployment | Runbook, flag stays OFF on merge, publish is a Founder act | sre-eng |
| DAS-1614 | Maintenance | Scheduled health/eval of the outbound endpoint | product-analyst |

**Feature flag note (no dedicated key exists yet):** the Planning child (DAS-1607)
decides between adding a new `a2a_outbound` key (default OFF) or reusing
`ws_d_langfuse_lens`. Recommendation carried into that ticket: **add a dedicated
`a2a_outbound` key** — A2A is a distinct trust boundary (external callers, not an
internal observability lens) and deserves its own rollback switch; reusing
`ws_d_langfuse_lens` would couple an unrelated kill-switch to this surface. The
Planning ticket makes this decision final and lands it.

## Acceptance criteria
- [ ] All eight children (DAS-1607..DAS-1614) closed, each through its own AADL stage gate.
- [ ] **FR-001:** the A2A endpoint exposes governed delivery only (extends OB-1) — an external caller cannot skip a gate or reach raw tools/agents.
- [ ] **FR-002:** an external submission is intaken only as a goal proposal, never a gate approval; it cannot write routing fields or self-approve (SC-001, SC-002).
- [ ] **FR-003:** publishing the endpoint is an explicit Founder act, logged to `board/.events.jsonl` (SC-003).
- [ ] **FR-004:** the endpoint is in-tenant only (TN-1); no external/hosted A2A relay or registry carries code/IP (SC-003).
- [ ] **FR-005:** the surface reuses the existing ADR-0009 admission + ADR-0012 redaction edge, no second admission path (SC-004).
- [ ] **FR-006:** the surface is feature-flagged OFF by default; with the flag OFF, dispatch/board behavior is byte-identical to pre-merge (SC-005).
- [ ] `diagnostics.py` 100/100; `board_lint`/`check_spec_consistency`/`check_dependency_graph` all green; no `project:` field on any A2A ticket (R9); committed wave attestation for every merged A2A PR.
- [ ] **Epic acceptance = AADL 6-gate closure for A2A OUTBOUND**, each gate logged in the stage-board, AND confirmation logged that WS-G's proof had landed before any child moved out of `backlog`.

## Log
### 2026-07-24 — Senior Product Manager
Created by `/daslab-plan` decomposition of the MUSTAQIL v3.0 A2A OUTBOUND interop
extension (ADR-0040 to be authored). Mirrored the WS-A REACH epic's AADL template
(DAS-1544) and the ADR-0036 OB-1…OB-4 invariants this extends. Contract = ADR-0040
(pending authorship in DAS-1607) + SPEC-009 (FR-001..FR-006, SC-001..SC-005).
Children DAS-1607..DAS-1614 — Design and Development each split into two tickets
(mirroring the WS-A split of Development into bridge + browser) to cover both
bracketed sub-items the dispatch contract named for each stage. `depends_on:
[DAS-1543]` mirrors WS-A's dependency on the MUSTAQIL program bootstrap (feature-flag
scaffold, TN-1 check) — already `done`. Deliberately did **not** add a `depends_on`
edge to any WS-B or WS-G ticket id: neither has an epic on the board yet, and
`check_dependency_graph.py` fails a dangling reference; the WS-B/WS-G sequencing
and the Q12 post-proof deferral are recorded as binding textual gates above instead,
with every child left in `status: backlog` (not `todo`) to signal "not yet
actionable by policy," re-opened only by an explicit orchestrator/CEO action once
WS-G's proof ships. No `project:` field — org-engine platform epic (board_lint R9).
This is a planning-only dispatch: no ADR authored, no code written, no ticket
executed — that is each child's own job when its gate opens.

### 2026-07-24 — Orchestrator (orchestrator-recorded)
**All eight children are now `done` (DAS-1607..DAS-1614), each through its own AADL
stage gate, flag OFF.** GATE-5 (DAS-1613) closed by SRE Lead and GATE-6 (DAS-1614)
by Product Analyst in this run; `a2a_outbound` reads `false` and `git diff
config/features.yaml` is empty — the surface is merged-but-dark, never published,
zero `a2a_publish` events.

**This epic is deliberately NOT being closed, and its last acceptance criterion is
NOT ticked.** That criterion reads: "confirmation logged that WS-G's proof had
landed before any child moved out of `backlog`." That confirmation cannot be
truthfully logged. WS-G's proof has **not** shipped: DAS-1595 (WS-G Deployment,
GATE-5) is `blocked` on an external dependency — no provisioned tenant Linux VM in
this session — and DAS-1596 (GATE-6) is blocked behind it. The A2A children were
worked ahead of the Q12 post-proof deferral this epic declared binding.

No agent may self-authorize that move, and the orchestrator will not retroactively
declare the gate open. **Founder decision required** — either (a) ratify the
out-of-order execution explicitly, at which point this criterion is amended to
record the waiver and the epic can close, or (b) hold the epic open until WS-G's
proof genuinely lands. Recorded honestly rather than closed quietly; the delivered
work itself is gate-verified and unaffected either way.

Follow-up DAS-1624 raised from DAS-1614's close report (two `scripts/`-zone items
its zone lock put out of reach). It does not reopen any closed A2A gate.
