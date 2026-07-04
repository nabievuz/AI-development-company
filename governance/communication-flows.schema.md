# communication-flows.yaml — file shape & derivation contract

> Schema doc for [`communication-flows.yaml`](communication-flows.yaml).
> Contract of record: [ADR-0026](../docs/adr/0026-communication-flows.md).
> Executable validator: [`scripts/validate_commflows.py`](../scripts/validate_commflows.py).

`governance/communication-flows.yaml` is a **derived, validatable** projection of
the org communication graph. It encodes who talks to whom as directional
`(sender → receiver)` edges so downstream LOOM tooling can reason over the org
graph instead of re-parsing prose. It is **never** a place to author new
topology: every edge is mechanically derived from a single source of truth, and
`scripts/validate_commflows.py` re-derives the whole edge set and rejects any
edge that does not trace back.

## Sources of truth (this file edits none of them)

| Source | What it contributes |
|---|---|
| [`board/ROUTING.md`](../board/ROUTING.md) | The reporting-line table — the canonical enumeration of the fleet role nodes and each role's manager/reviewer. Every edge derives from here. |
| [`org/schema.daslab.yaml`](../org/schema.daslab.yaml) | `routing.escalation: [ic, lead, cxo, founder]` — the tier escalation ladder, cross-checked; its terminal `founder` rung is the external boundary. |
| [`governance/policies/raci.md`](policies/raci.md) | The RACI decision matrix. Its `C` (Consulted) relationships are a **future** `consult` kind — see [Deferred: consult edges](#deferred-consult-edges). |

## File shape

```yaml
version: 1              # integer >= 1
flows:                  # non-empty list of directional edges
  - sender: cto         # fleet role key from board/ROUTING.md
    receiver: backend-em
    kind: delegation    # down the reporting chain: manager -> report
    source: routing.reports_to
  - sender: backend-em
    receiver: cto
    kind: escalation    # up the reporting chain: report -> manager
    source: routing.reports_to
```

### Fields (per edge — all four required, no others)

| Field | Type / enum | Meaning |
|---|---|---|
| `sender` | fleet role key ∈ `board/ROUTING.md` | the role that originates the message |
| `receiver` | fleet role key ∈ `board/ROUTING.md` | the role that receives it |
| `kind` | `delegation` \| `escalation` | direction relative to the reporting chain |
| `source` | `routing.reports_to` \| `schema.escalation` | provenance: which SSOT the edge derives from |

### Closed enums

- **`kind`** ∈ `{delegation, escalation}` exactly. `delegation` runs **down** the
  reporting chain (a manager to a direct report); `escalation` runs **up** it (a
  report to its manager). Any other value is a validator error.
- **`source`** ∈ `{routing.reports_to, schema.escalation}`.
- **`sender` / `receiver`** must be role keys present in `board/ROUTING.md`. The
  string `founder` is **forbidden** as a sender or receiver.

## Derivation & validation rules

`scripts/validate_commflows.py` enforces (ADR-0026 §1 rules 1–4):

1. **Role-node closure** — every `sender`/`receiver` is one of the fleet roles in
   `board/ROUTING.md`; `founder` never appears.
2. **Reporting-line completeness + soundness** — for each `ROUTING.md` row
   `report → manager` whose reviewer is a fleet role (not `—`), the file holds
   **exactly two** edges: `delegation(manager → report)` and
   `escalation(report → manager)`, both `source: routing.reports_to`. No more, no
   fewer, no duplicates. Roles whose reviewer is `—` (`chairman`, `board-member`)
   have no upward fleet edge — the chain terminates at the top of the fleet.
3. **Escalation-ladder consistency** — the `schema.routing.escalation` ladder is
   present and terminates in the external `founder` rung; that rung emits no
   fleet edge.
4. **No invented topology** — the authored edge set equals the set re-derived
   purely from the SSOTs. Any extra or missing edge is an error, so the file is a
   pure function of the sources and drift is caught, not silently tolerated.

The file is generated from the sources and must be regenerated whenever a
`ROUTING.md` reporting line changes:

```sh
python3 scripts/validate_commflows.py --emit > governance/communication-flows.yaml
python3 scripts/validate_commflows.py            # re-validate (exit 0)
```

## founder is an external gate, not a node

Per [ADR-0026 §3](../docs/adr/0026-communication-flows.md), the founder is the
**external human approval boundary the fleet escalates INTO**, sitting *above*
`chairman`. It is the terminal rung of the escalation ladder and a GATE-1 signer,
but it is **not** one of the fleet agent roles and has no `ROUTING.md` row.
Therefore `communication-flows.yaml` never emits `founder` as a `sender` or
`receiver`; the fleet's escalation edges terminate at the top of the in-fleet
chain (`chairman` / `board-member`, whose reviewer is `—`), and the step up to
the founder is the human boundary, not a machine edge.

## Deferred: consult edges

RACI *consult* (`C`) relationships from
[`governance/policies/raci.md`](policies/raci.md) are a natural sideways-edge
extension, but v1 keeps the `kind` enum **closed** to `{delegation, escalation}`
for validatability. Per [ADR-0026 §Consequences](../docs/adr/0026-communication-flows.md),
`consult` is deferred to a future `kind` introduced by a later ADR/ticket — not
added ad hoc here. The validator therefore rejects any `consult` edge today.
