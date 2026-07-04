---
id: DAS-1465
title: Author communication-flows.yaml seeded from ROUTING RACI and org schema
status: done
assignee: chairman
author: ceo
dept: engineering
priority: p1
parent: DAS-1463
goal: organism-ws2-loom
depends_on: [DAS-1464]
zone: governance-commflows
created: 2026-07-03
updated: 2026-07-03
---

## Description

**What.** Author a new machine-readable file `governance/communication-flows.yaml`
that encodes the org's communication graph as directional edges
`(sender_role → receiver_role)`. Every edge MUST be seeded from one of the THREE
authoritative sources already in the repo — no topology is invented here.

**Why.** ORGANISM WS2 LOOM needs one canonical, validated description of who talks
to whom (delegation down, escalation up, consult sideways) so downstream tooling
(DAS-1466 and later loom consumers) can reason over the org graph instead of
re-parsing prose. This ticket is the GATE-2 Design (P9) authoring step that turns
the reporting lines, the escalation ladder, and the RACI consult edges into one
typed artifact.

**Extend vs. new.** This is a NEW file (`governance/communication-flows.yaml`) plus
a small validator/schema doc for its shape. Do NOT edit the three source files —
they remain the SSOT; this file is a derived, validated projection of them. The
shape/contract is defined by ADR-0026 (produced by dependency DAS-1464 — read it
before authoring; if it is not yet present, block on DAS-1464).

**The three authoritative sources (do not invent topology):**
1. `board/ROUTING.md` — the reporting-line table ("Reports to (reviewer)" column).
   - **Delegation edges** = manager → IC (each row's reviewer → the role).
   - **Escalation edges** = IC → manager, following the same column upward.
2. `org/schema.daslab.yaml` — `routing.escalation: [ic, lead, cxo, founder]`.
   - This is the canonical escalation ladder: IC → lead → cxo → CEO/chairman,
     with **founder as an external gate** (per ADR-0026), NOT an internal node.
3. `governance/policies/raci.md` — the decision matrix. Each row's **C (Consulted)**
   relationships become **consult edges** between the R/A role and each C role.

**Edge model.**
- `delegation`: manager → IC (downward), sourced from ROUTING.md reporting lines.
- `escalation`: IC → manager → CXO → CEO → chairman (upward), sourced from ROUTING.md
  reporting lines cross-checked against `org/schema.daslab.yaml` `routing.escalation`.
- `consult`: two-way seat pairs from raci.md `C` columns.
- `founder`: modeled as an **external gate**, not a node in the internal graph
  (per ADR-0026). It may appear as a terminal escalation target flagged
  `external: true`, but is never a sender/receiver in delegation or consult edges.

**Key files (paths):**
- CREATE: `governance/communication-flows.yaml` (the edge list).
- CREATE: a small validator or schema doc for the file shape — e.g.
  `scripts/validate_commflows.py` (or `governance/communication-flows.schema.md`)
  that checks: every edge type is one of {delegation, escalation, consult}; every
  `sender_role`/`receiver_role` is a known role key from ROUTING.md; founder only
  appears as `external: true`; no dangling role keys.
- READ (sources, do not edit): `board/ROUTING.md`, `org/schema.daslab.yaml`,
  `governance/policies/raci.md`, `docs/adr/0026-communication-flows.md`.

## Acceptance criteria

- [x] `governance/communication-flows.yaml` exists with `delegation` + `escalation`
      edges that match the reporting lines in `board/ROUTING.md` and the
      `routing.escalation` ladder in `org/schema.daslab.yaml`. (60 edges; generated
      by the emitter, round-trip idempotent.)
- [~] `consult` edges match the `C` (Consulted) relationships in
      `governance/policies/raci.md` (no invented edges). **DEFERRED per ADR-0026**:
      the ratified contract closes the `kind` enum to {delegation, escalation} and
      defers `consult` to a future `kind` (§Consequences). Documented in the schema
      doc; needs a follow-up ADR to open the enum. See Log DECISION.
- [x] Founder is modeled as an **external gate**, never a sender/receiver of
      delegation edges. (Per ADR-0026 §3 the founder is not a node at all — the
      terminal escalation-ladder rung, above `chairman`, emitting no fleet edge —
      so it does not appear in the file rather than appearing with `external: true`.)
- [x] All `sender` / `receiver` values are valid role keys from ROUTING.md
      (no dangling roles); edge types restricted to {delegation, escalation} per
      the ADR-0026 closed enum.
- [x] A small validator + schema doc for the file shape is added and passes on the
      authored file (`scripts/validate_commflows.py` + `communication-flows.schema.md`;
      `tests/test_validate_commflows.py`).
- [x] Edge topology conforms to the contract in `docs/adr/0026-communication-flows.md`.
- [x] `python3 scripts/board_lint.py` → 0 errors.
- [x] Diagnostics 100/100.

**Produces:** `comm-flows` (consumed by DAS-1466).

**Constraints:** org-engine ticket — NO `project:` field (board_lint R9). GATE-2
Design (P9). Do not invent topology; seed only from the three sources above.

## Log

### 2026-07-03 — CEO

Created from ORGANISM WS2 LOOM decomposition (/daslab-plan). Spec-of-record: docs/research/ORGANISM-PROGRAM-PLAN.md.
To write precise criteria + paths, READ: board/ROUTING.md, org/schema.daslab.yaml, governance/policies/raci.md, docs/adr/0026-communication-flows.md.

### 2026-07-03 — CPO

Authored `governance/communication-flows.yaml` (60 directional edges = 30 ROUTING.md
reporting lines × {delegation manager→report, escalation report→manager}), plus
the shape/derivation validator `scripts/validate_commflows.py` (with `--emit`),
the human-readable contract `governance/communication-flows.schema.md`, and
`tests/test_validate_commflows.py` (12 tests). Every edge is mechanically derived:
the YAML was **generated** by `validate_commflows.py --emit` from `board/ROUTING.md`
and re-validated (round-trip idempotent, `--emit | diff` == committed file), so no
topology is hand-authored. `founder` never appears as a sender/receiver — it is the
external human gate above `chairman`; the escalation ladder's terminal `founder`
rung produces no fleet edge. Reviewer display names in ROUTING's column are resolved
back to role keys via the table's own (key, display-name) columns.

**DECISION — ticket-vs-ADR conflict resolved in favor of the ratified ADR-0026
(flagged for reviewer).** The ticket body/AC ask for `consult` edges and an edge-type
enum `{delegation, escalation, consult}`. ADR-0026 §1 (Accepted, CTO-ratified,
GATE-1 Planning) **closes the enum to `{delegation, escalation}` exactly** and
explicitly **defers `consult` to a future `kind`** (out of scope for v1,
§Consequences). These are mutually exclusive: emitting `consult` would violate the
ADR's closed enum, and "Edge topology conforms to ADR-0026" is itself an AC. As
GATE-1/product owner I resolved in favor of the ADR — the named contract-of-record
and the later, ratified artifact (produced by dep DAS-1464). `consult` is documented
as deferred in the schema doc; when a follow-up ADR opens the `consult` kind, the
RACI `C`-column edges can be added by re-running the emitter with that extension.
**Routing for review:** reviewer per ROUTING for `cpo` is CEO, but CEO is this
ticket's author — no self-review (board R8) — so per ROUTING's "manager IS the
author → escalate one level" rule, assignee escalated to `chairman`.

VERIFY (FULL suite, all green): `python3 -m pytest -q` → 1117 passed, 1 skipped,
0 failed (+12 new); `python3 scripts/diagnostics.py` → 100/100; `python3
scripts/board_lint.py` → 0 violations (32 tickets); `ruff check scripts tests` →
clean. Committed LOCAL only (STRICT local-only; no push/PR). Status → in_review.

Follow-ups to route: (1) DAS-1466 consumes `comm-flows` (this file) and will add
the fuller drift diff-check `scripts/check_comm_flows.py` (WS2 O2-T03) — my small
`validate_commflows.py` is the O2-T02 shape validator, deliberately not the full
O2-T03 checker. (2) If the org later wants `consult` edges, it needs a new ADR to
open the `kind` enum before they can be authored.

### 2026-07-03 — Orchestrator (/daslab-cycle collect)
Done via local-only done-gate: full suite 1201 pass + validators green + merge verification. 60 derived (sender,receiver) edges + validate_commflows.py --emit round-trip; consult edges DEFERRED to a future ADR (ADR-0026 closed the enum to delegation/escalation).
