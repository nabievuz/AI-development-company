# ADR 0026 — Communication-flows format + GATE-1/GATE-6 owner reconciliation (founder is an external gate, not a fleet node)

- **Status:** Accepted (**CTO — decider; RACI 3.1 A (ADR ratifier); AADL GATE-1 Planning artifact — 2026-07-03**)
- **Date:** 2026-07-03
- **Scope:** Platform / org-graph — the schema of record for `governance/communication-flows.yaml` and the reading rule for AADL gate ownership; a **decision doc only** (no runtime routing change ships here).
- **Deciders:** **CTO (accountable)** — ADR/architecture authority (RACI 3.1). CEO consulted (WS2 planning owner, ticket author).
- **Relates:** ORGANISM WS2 LOOM (`docs/research/ORGANISM-PROGRAM-PLAN.md` §WS2 O2-T01, §9 Q1/Q2). Cites — but does **not** edit — `governance/policies/ai-agent-lifecycle.md` §1 (the Accountable SSOT), `org/schema.daslab.yaml` (`roles[*].gate_owner`, `routing.escalation` — the signer-set + escalation-ladder SSOT), and `board/ROUTING.md` (the reporting-line SSOT and the enumeration of fleet role nodes). Builds on the RACI matrix `governance/policies/raci.md`.
- **Supersedes / Amends:** nothing. This ADR **interprets and reconciles** existing SSOTs by reference; it mutates none of them. (The WS2 plan text names this artifact "ADR-0025"; the append-only numbering rule already assigned 0025 to *events-load-bearing*, so this decision takes the next free number, **0026**.)

> WS2 LOOM needs one unambiguous decision of record before it can generate and
> validate a machine-readable `governance/communication-flows.yaml`. Today two
> things are undecided: (1) the exact YAML shape of the flows file, (2) whether
> the GATE-1/GATE-6 owner discrepancy between the AADL RACI and the org schema is
> a conflict, and (3) whether `founder` is a node in the routing graph. This ADR
> fixes all three. **No dispatch behaviour changes on merge** — it is a Planning
> (GATE-1) artifact that the downstream WS2 tickets (O2-T02 authoring the file,
> O2-T03 `check_comm_flows.py`) build against.

## Context

The org communication topology already exists, spread across three
single-sources-of-truth (SSOTs):

- **`board/ROUTING.md`** — the reporting lines. Each row gives a role key and the
  role it *reports to* (its reviewer/manager). This is the fleet reporting chain
  and the canonical enumeration of the **32 agent role nodes**. It has **no
  `founder` row**.
- **`org/schema.daslab.yaml`** — `routing.escalation: [ic, lead, cxo, founder]`
  (the tier-level escalation ladder) and `roles[*].gate_owner` (which AADL gates
  each role *signs*).
- **`governance/policies/ai-agent-lifecycle.md` §1** — the AADL RACI table: for
  each of the six gates, the single **Accountable** role (plus Responsible /
  Consulted).

WS2 wants a derived, validatable view of this graph — `communication-flows.yaml`
— so that a validator (`check_comm_flows.py`, O2-T03) can (a) reject any
ticket/dispatch that routes along an edge the org graph does not contain, and (b)
diff the file against the SSOTs so it can never drift into invented topology. Two
questions block writing that file:

1. **The GATE-1/GATE-6 owner discrepancy (§9 Q1).** Read naïvely the two sources
   disagree:
   - AADL RACI: GATE-1 Accountable = `cpo`; GATE-6 Accountable = `coo`.
   - Schema `gate_owner`: GATE-1 signers = `{founder, cpo}`; GATE-6 signers =
     `{cto}`.
   If `gate_owner` were read as "a second Accountable", GATE-1 would have two
   Accountables (`cpo` and `founder`) and GATE-6 would name `cto` where RACI names
   `coo` — an apparent `A↔A` clash (RACI §Conflict-resolution #3). It is not a
   real clash; the two lists answer **different questions**, and that must be
   written down before the flows file cites either.

2. **Is `founder` a comm-flow node? (§9 Q2).** The founder is the terminal rung of
   the escalation ladder and a GATE-1 signer, yet appears in **no** `ROUTING.md`
   row and is **not** one of the 32 fleet agent roles. Whether the flows graph
   emits `founder` as a sender/receiver must be decided so edges are well-typed.

**AADL stage.** GATE-1 Planning. This is an ADR (a decision doc) — a Planning
deliverable that fixes the format and the reading rule; it ships no runtime
routing change.

**Extend-vs-new posture (binding).** INTERPRET, do not mutate. This ADR edits
neither `ai-agent-lifecycle.md` nor `org/schema.daslab.yaml` nor `board/ROUTING.md`
— they remain the SSOTs. It records how a reader reconciles them and specifies a
new *derived* artifact (`communication-flows.yaml`) that must always be
regenerable from them.

## Decision

### 1. The `communication-flows.yaml` format — a derived, directional-edge view

`governance/communication-flows.yaml` is a **derived** file: every edge is
mechanically justified by one of the three SSOTs, and a validator MUST be able to
diff it against them. It is never a place to author new topology (O2-T02:
"do not invent topology").

**Shape.** A `version` integer and a top-level `flows:` list. Each list item is
one **directional edge** — a `(sender, receiver)` ordered pair — with these
fields:

| Field | Required | Type / enum | Meaning |
|---|---|---|---|
| `sender` | yes | role key ∈ `board/ROUTING.md` fleet roles | the role that originates the message |
| `receiver` | yes | role key ∈ `board/ROUTING.md` fleet roles | the role that receives it |
| `kind` | yes | `delegation` \| `escalation` | direction relative to the reporting chain |
| `source` | yes | `routing.reports_to` \| `schema.escalation` | provenance: which SSOT the edge derives from |

```yaml
# governance/communication-flows.yaml
# DERIVED + VALIDATABLE view of the org graph — regenerable from the SSOTs.
# NEVER hand-author new topology here; edges must trace to ROUTING.md /
# schema.daslab.yaml. Validated by scripts/check_comm_flows.py (WS2 O2-T03).
version: 1
flows:
  - sender: cto            # a fleet role key from board/ROUTING.md
    receiver: backend-em
    kind: delegation        # down the reporting chain: manager -> report
    source: routing.reports_to
  - sender: backend-em
    receiver: cto
    kind: escalation        # up the reporting chain: report -> manager
    source: routing.reports_to
```

**Enums (closed sets).**
- `kind` ∈ **{`delegation`, `escalation`}** exactly. `delegation` runs **down** the
  reporting chain (a manager to a direct report); `escalation` runs **up** it (a
  report to its manager). Any other value is a validator error. (RACI *consult*
  edges are explicitly **out of scope for v1** — a possible future `kind`, not
  emitted now.)
- `source` ∈ **{`routing.reports_to`, `schema.escalation`}** — the SSOT the edge is
  derived from, so the diff-check knows what to compare each edge against.
- `sender`, `receiver` — MUST be role keys present in `board/ROUTING.md`. The
  string `founder` is **forbidden** as a `sender` or `receiver` (see §3).

**Derivation / validation rules** (what `check_comm_flows.py` enforces):
1. **Role-node closure.** Every `sender`/`receiver` is one of the 32 fleet roles in
   `ROUTING.md`. `founder` never appears.
2. **Reporting-line completeness + soundness.** For each `ROUTING.md` row
   `report → manager` where `manager` is a fleet role (i.e. the reviewer is not
   `—`), the file contains **exactly two** edges and no more:
   `delegation(sender=manager, receiver=report)` and
   `escalation(sender=report, receiver=manager)`, both `source: routing.reports_to`.
   Roles whose reviewer is `—` (`chairman`, `board-member`) have no upward fleet
   edge — the chain terminates at the top of the fleet.
3. **Escalation-ladder consistency.** Every `escalation` edge climbs exactly one
   rung of `schema.routing.escalation` (`ic → lead → cxo`); an edge that skips a
   rung or descends is an error. The `founder` rung of the ladder is the external
   boundary (§3) and produces **no** fleet edge.
4. **No invented topology.** Any edge that does not trace to a `ROUTING.md`
   reporting line or a `schema.escalation` rung is rejected. The file is thus a
   pure function of the SSOTs; drift is a CI failure, not a silent divergence.

### 2. GATE ownership — RACI is the single Accountable; schema `gate_owner` is the signer set

The two sources are **complementary, not conflicting**, because they answer
different RACI questions. Fixed rule:

> **The AADL RACI (`ai-agent-lifecycle.md` §1) is AUTHORITATIVE for the single
> `Accountable` per gate. `org/schema.daslab.yaml:roles[*].gate_owner` is the
> `signer set` — the roster of roles whose sign-off is *collected/recorded* at
> that gate. `gate_owner` is NOT a second Accountable.**

Applied to the two contested gates:

| Gate | Accountable (AADL RACI — authoritative, exactly one) | Signer set (schema `gate_owner` — roster) |
|---|---|---|
| GATE-1 Planning | `cpo` | `{founder, cpo}` |
| GATE-6 Maintenance | `coo` | `{cto}` |

Reading it this way, **no `A↔A` claim exists** and RACI §Conflict-resolution #3
is not triggered:
- **GATE-1:** `cpo` is *both* the single Accountable *and* a signer; `founder` is a
  signer only (an external human approval — see §3), never a competing Accountable.
- **GATE-6:** `coo` is the single Accountable (owns the maintenance outcome); `cto`
  is the recorded signer (the technical sign-off collected at the gate). Different
  RACI dimensions on the same gate — an Accountable and a signer are orthogonal
  roles, so `coo ≠ cto` is not a contradiction.

`communication-flows.yaml` (and any gate-ownership reader) therefore reads **both**
SSOTs and keeps them in their own lanes: the **Accountable** comes from AADL RACI,
the **signer roster** from the schema. Neither overwrites the other; a consumer
that needs "who owns this gate" reads RACI, one that needs "whose signatures are
collected" reads the schema. This ADR mutates neither file — it fixes the reading
rule so the derived view cites each correctly.

### 3. `founder` is an external human gate ABOVE the chairman — NOT a fleet routing node

The founder is modeled as the **external human approval boundary the fleet
escalates INTO**, sitting **above `chairman`**. Concretely:

- The founder is the terminal rung of `schema.routing.escalation`
  (`[ic, lead, cxo, founder]`) and a GATE-1 signer — but is **not** one of the 32
  agent roles: `board/ROUTING.md` lists **no `founder` row**.
- Therefore `communication-flows.yaml` **does NOT emit `founder` as a `sender` or
  `receiver`** agent node. The fleet's escalation edges terminate at the top of the
  in-fleet chain (`chairman` / `board-member`, whose reviewer is `—`); the step
  from the fleet up to the founder is the human boundary, not a machine edge in the
  graph.
- This is consistent with the rest of the platform: the founder is the human who
  authorizes new goals (QONUN-3), flips feature flags (QONUN-5), and answers
  interrupt cards — always an *external* actor the automated fleet defers to, never
  an automated role the dispatcher can route work to.

## Consequences

**Positive.**
- WS2 O2-T02 can author `governance/communication-flows.yaml` against a fixed,
  closed-enum schema, and O2-T03 (`check_comm_flows.py`) can diff it against the
  three SSOTs — an undeclared route becomes structurally unrepresentable and CI-
  caught, with no place to smuggle invented topology.
- The GATE-1/GATE-6 "discrepancy" is retired as a *category error*, not patched by
  editing an SSOT: RACI keeps its single-Accountable invariant, the schema keeps
  its signer roster, and the flows file cites each in its own lane.
- `founder` has one written status across the platform: an external human gate
  above the chairman, never a routing node — so no generator, validator, or
  dispatcher will ever try to route a ticket *to* the founder as if it were an
  agent.

**Negative / accepted.**
- `communication-flows.yaml` is a **derived** artifact and must be regenerated
  whenever a `ROUTING.md` reporting line or the escalation ladder changes;
  otherwise the O2-T03 diff-check fails. Accepted — that failure is the point (it
  forbids drift). It adds one generated file to keep in sync, paid for by making
  undeclared routes impossible.
- v1 encodes only `delegation`/`escalation` edges; RACI *consult* edges (a WS2
  stretch in O2-T02) are deferred to a future `kind`. Accepted — the enum is closed
  now for validatability and extended by a later ADR/ticket, not by ad-hoc files.

**Law check.**
- **Charter / RACI** — the CTO is the ADR ratifier (RACI 3.1 A; IC authors, MGR
  reviews, CTO ratifies); this ADR is decided by the CTO. It does not amend the
  RACI matrix — it records how to *read* the AADL RACI against the schema.
- **AADL** — a GATE-1 Planning artifact for ORGANISM WS2; no gate skipped; ships no
  runtime routing change. It reaffirms §1 as the authoritative Accountable source.
- **Board audit / governance-as-policy** — no SSOT is edited in place
  (`ai-agent-lifecycle.md`, `org/schema.daslab.yaml`, `board/ROUTING.md`
  untouched); the reconciliation is recorded here by reference, so the append-only
  audit trail holds. No never-auto-approve category is triggered (a decision doc,
  not a policy/schema mutation).
- **Project placement** — a platform-level ADR under `docs/adr/`; no project
  artifact written; `board/tickets/` ticket carries no `project:` field.
- **Model allocation** — unchanged; CTO on opus per the table.

## Enforcement / acceptance

- This ADR is decided by the **CTO** (RACI 3.1, GATE-1 Planning) and is `Accepted`
  on merge.
- The format in §1 is the contract O2-T02 (`communication-flows.yaml`) and O2-T03
  (`check_comm_flows.py`) implement and enforce. The four derivation/validation
  rules are the executable form of "derived, not invented".
- §2 is the citation any future "is `gate_owner` a second Accountable?" question
  resolves to: **no** — AADL RACI is the single Accountable, the schema is the
  signer set.
- §3 is the citation for "is `founder` a routing node?": **no** — external human
  gate above the chairman, never emitted as a `sender`/`receiver`.
