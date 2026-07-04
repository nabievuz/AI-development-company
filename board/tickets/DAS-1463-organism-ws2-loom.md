---
id: DAS-1463
title: ORGANISM WS2 — LOOM (typed orchestration)
status: done
assignee: cto
author: ceo
dept: engineering
priority: p1
parent: 
goal: organism-ws2-loom
created: 2026-07-03
updated: 2026-07-03
---

## Description

**EPIC.** WS2 — LOOM turns DasLab from a static dispatch engine into a **self-planning,
typed orchestration** organism. It kills two v1.0.0 capability gaps and lands four
clean-room patterns:

- **Kills G3** (no dynamic planner) and **G4** (no typed contracts between agents).
- **P7 — dual-ledger planner:** a per-run *task-ledger* (facts/plan) plus a per-wave
  *progress-ledger* the opus planner emits, with a stall rule that triggers bounded
  replanning.
- **P8 — typed produces/consumes:** frontmatter `produces:`/`consumes:` fields validated
  against `governance/schemas/*.yaml`; a schema-mismatched wave plan fails lint.
- **P9 — communication-flows:** directional `(sender,receiver)` routing that is
  schema-enforced — an undeclared agent→agent route is structurally unrepresentable in the
  generated subagent defs AND caught by a validator.
- **P10 — guardrail tripwires:** per-role guardrails that re-dispatch the same agent on a
  trip (bounded) then escalate; input guardrails screen scope before accept.

**Why now / build order.** Per the spec-of-record §2, the strict dependency chain is
`WS1 → WS3(seam) → WS2 → WS4 → …`. Durable execution (WS1) and the telemetry seam (WS3)
come first; WS2 is the autonomy layer that sits on top of a crash-safe, observable
substrate. WS2 is therefore unblocked only once WS1/WS3 emit real paired events.

**Extend-vs-new (do not duplicate).** WS2 is disciplined *extension* wherever an asset
already exists:
- **extend** `scripts/board_lint.py` — `VALID_STATUSES` frozenset + R-rules; regex parser
  needs a tolerant structured reader for the new typed fields (do not fork a second parser
  if one can be unified — see O2-T04).
- **extend** `scripts/check_dependency_graph.py` — optional `depends_on:`/`zone:` acyclic,
  non-dangling graph; WS2 typed producer/consumer edges extend it.
- **extend** `scripts/gen_subagents.py` (+ `scripts/check_agents_sync.py` guard) — compile
  each agent's ALLOWED routes into its generated def.
- **new** `governance/communication-flows.yaml`, `governance/schemas/*.yaml`,
  `governance/guardrails/<role>.py`, `scripts/check_comm_flows.py`, `scripts/check_ledger.py`,
  `board/runs/<id>/task-ledger.md`, `board/runs/<id>/progress-ledger.json`.

**Key files (paths):**
- Spec-of-record: `docs/research/ORGANISM-PROGRAM-PLAN.md` §4 WS2 (rows O2-T01..O2-T08),
  §5 contract row 9, §9 Founder decisions.
- AADL policy: `governance/policies/ai-agent-lifecycle.md` (§2 skeleton; 6-gate closure).
- Extension points: `scripts/board_lint.py`, `scripts/check_dependency_graph.py`,
  `scripts/gen_subagents.py`, `scripts/check_agents_sync.py`, `.claude/agents/*`,
  `ROUTING.md`, `org/schema.daslab.yaml`, `governance/raci.md`.
- New surfaces: `governance/communication-flows.yaml`, `governance/schemas/`,
  `governance/guardrails/`, `scripts/check_comm_flows.py`, `scripts/check_ledger.py`,
  `board/runs/`.
- New ADR: ADR-0025 (comm-flows format + gate-owner reconciliation).

**Children:** DAS-1464..DAS-1471 (one per O2-T01..O2-T08).

| Child | Stage | Ticket | Owner-hint |
|---|---|---|---|
| DAS-1464 | Planning | O2-T01 — ADR-0025 comm-flows format + resolve GATE-1/6 owner reconciliation (§9 Q1) + founder-node question (§9 Q2) | cto + ceo |
| DAS-1465 | Design | O2-T02 — `governance/communication-flows.yaml` directional edges seeded from `ROUTING.md` reporting lines + `schema.daslab.yaml` escalation ladder + `raci.md` consult edges (do not invent topology) | cpo |
| DAS-1466 | Development | O2-T03 — `gen_subagents.py` compiles ALLOWED routes into each generated def (undeclared route structurally unrepresentable); `check_comm_flows.py` fails any ticket/dispatch on an undeclared route (P9) | backend-em |
| DAS-1467 | Design | O2-T04 — Typed contracts (P8): frontmatter `produces:`/`consumes:` → `governance/schemas/*.yaml` (pydantic-backed); unify the 3 frontmatter parsers or add one tolerant structured reader | backend-em |
| DAS-1468 | Development | O2-T05 — `board_lint`/`check_dependency_graph` fail a wave plan when a consumer has no producer, or the dep graph is disconnected/cyclic | backend-eng-2 |
| DAS-1469 | Development | O2-T06 — Task-ledger (P7a): per-run `board/runs/<id>/task-ledger.md` (given/known/to-look-up/guesses + plan) | senior-pm |
| DAS-1470 | Development | O2-T07 — Progress-ledger (P7b): opus planner emits `progress-ledger.json` per wave; `check_ledger.py` validates `{request_satisfied,in_loop,progress_being_made,next_tickets[],instruction}`; stall rule `in_loop\|\|!progress→stall+1 else max(0,stall-1)`; `stall>3`→regenerate task-ledger + `REPLANNED` event; bounded `max_replans`→interrupt-card | senior-pm + backend-em |
| DAS-1471 | Development | O2-T08 — Guardrail-tripwires (P10): per-role `governance/guardrails/<role>.py`→`(ok,feedback)`; dispatch wrapper re-dispatches SAME agent on trip (max 2) then escalates; input guardrails screen scope pre-accept | security-lead + qa-lead |

**Approved §9 defaults (binding for children):**
- **GATE-1/6 owner = AADL RACI Accountable + org/schema signer-set** (the reconciled
  canonical owner set — ADR-0025 encodes it).
- **Founder = external human gate above chairman**, NOT a communication-flow node (the
  founder never appears as a `(sender,receiver)` vertex in `communication-flows.yaml`).

## Acceptance criteria

- [ ] All eight children (DAS-1464..DAS-1471) closed, each through its own AADL stage gate.
- [ ] **P9 headline (§5 contract row 9):** an undeclared agent→agent route is both
      *structurally unrepresentable* in the generated subagent defs AND *caught* by
      `scripts/check_comm_flows.py` — verifiable by a negative test that fails a dispatch on
      an undeclared route.
- [ ] **P8:** a wave plan whose `produces:`/`consumes:` contract mismatches its schema
      fails lint with an actionable error message.
- [ ] **P8/dep-graph:** `board_lint`/`check_dependency_graph` fail a wave plan when a
      consumer has no producer, or the graph is disconnected/cyclic — actionable error.
- [ ] **P7 dual-ledger:** a stalled run replans within ≤2 waves and pauses (interrupt-card)
      after the `max_replans` budget; `check_ledger.py` validates the progress-ledger schema
      and stall rule.
- [ ] **P10:** a failing ticket self-corrects within ≤2 re-dispatches of the SAME agent or
      escalates; input guardrails screen scope pre-accept.
- [ ] `communication-flows.yaml` edges match all three sources (`ROUTING.md`,
      `org/schema.daslab.yaml`, `governance/raci.md`) — no invented topology.
- [ ] ADR-0025 merged, encoding the reconciled GATE-1/6 owner set and the founder-external-
      gate decision; ADRs updated in the Planning gate.
- [ ] Founder = external human gate above chairman is honored: founder is NOT a comm-flow
      vertex anywhere in the config or generated defs.
- [ ] `python3 scripts/gen_subagents.py` regenerated and `scripts/check_agents_sync.py`
      green (no drift) after route compilation.
- [ ] `diagnostics.py` 100/100; `board_lint.py` green; zero QONUN violations; no donor
      imports/code; no `project:` field on any WS2 board ticket (board_lint R9).
- [ ] **Epic acceptance = AADL 6-gate closure for WS2** (Planning → Design → Development →
      Testing → Deployment → Maintenance), each gate closed by its GATE checklist and logged
      in the stage-board.

## Log

### 2026-07-03 — CEO
Created from ORGANISM WS2 LOOM decomposition (/daslab-plan). Spec-of-record: docs/research/ORGANISM-PROGRAM-PLAN.md.
Scope confirmed against §4 WS2 (O2-T01..O2-T08), §5 contract row 9 (headline acceptance:
undeclared agent→agent route unrepresentable + validator-caught), and the approved §9
defaults (GATE-1/6 owner = AADL RACI Accountable + org/schema signer-set; founder = external
human gate above chairman, not a comm-flow node). Children DAS-1464..DAS-1471. Org-engine
ticket — no `project:` field (board_lint R9). Epic acceptance = AADL 6-gate closure for WS2.

### 2026-07-03 — Orchestrator (/daslab-run)
Done. EPIC CLOSED — WS2 LOOM complete. ADR-0026 comm-flows+gate-owner reconciliation; communication-flows.yaml; compiled routes + check_comm_flows (§5 row 9); typed produces/consumes + board_lint R11 + dep-graph validation; task-ledger + progress-ledger stall->replan; guardrail tripwires. Children DAS-1464..1471 done.
