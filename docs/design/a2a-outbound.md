# A2A outbound design — goal-proposal intake (never an approval), publish-is-a-Founder-act, in-tenant boundary; one governed edge reused

- **Status:** Design (AADL Stage 2 — GATE-2) — awaiting review (CTO accountable; Security Lead consulted — proposal-not-approval, admission/redaction reuse, in-tenant boundary, Founder-only publish RBAC)
- **Date:** 2026-07-24
- **Tickets:** DAS-1608 (A2A Design — goal-proposal intake, §1) **and** DAS-1609 (A2A Design — publish-is-a-Founder-act + in-tenant boundary, §2); epic DAS-1606 (MUSTAQIL A2A OUTBOUND). One doc covers both design halves — both are `zone: docs/design`, so a single file avoids a same-file collision.
- **Author:** Backend EM (responsible); CTO (accountable stage owner, GATE-2); Security Lead (consulted — QONUN-5 proposal-not-approval, ADR-0009 admission + ADR-0012 redaction reuse, TN-1 boundary, Founder-only publish RBAC mirroring TN-3)
- **Binds to:** ADR-0040 (A2-1…A2-6, **Accepted** 2026-07-24 — CTO author+ratify, RACI 3.1/3.6 A, same owner as ADR-0036), `docs/specs/009-mustaqil-a2a-outbound/SPEC.md` (FR-001…FR-006 / SC-001…SC-005, reviewed 2026-07-24 at GATE-1), which A2A **extends** — ADR-0036 (OB-1…OB-4, the outbound interop surface A2A is a slice of), ADR-0009 (harness-owns-transport / admission-layer ceiling — reused, not re-opened), ADR-0012 (M/B/F content-classification + redaction at the boundary — reused), ADR-0038 (TN-1 in-tenant only; TN-3 Founder-identity RBAC, agent identity never holds gate/publish authority), ADR-0033 (TB-4 untrusted-ingress discipline for a caller payload), ADR-0019 (feature flag OFF by default), ADR-0024/0025 (event store canonical; a caller submission is derived intake, never truth), ADR-0027 (never-auto-approve / NOT-a-daemon). **Reuses verbatim** — the ADR-0009 admission edge the ADR-0036 outbound surface already uses (no second entry path), the ADR-0012 §2 scrubber, `scripts/check_in_tenant.py` + `config/tenant_boundary.yaml` (TN-1 guard), `scripts/rbac.py` `decide()` (Founder-only publish, WS-E SSOT), and the `board/goal-inbox/` candidate-queue landing the WS-H control plane already writes goal proposals into (`docs/design/ws-h-control-plane.md` §3). Founder discovery answers Q10 (internal self-host), Q6 (Founder-only approval), Q12 (defer live publish until after the WS-G proof — a go-live gate, not a build blocker).
- **Downstream:** DAS-1610 (A2A Development — outbound endpoint, `zone: tools/a2a`: stands up the governed surface, wires the ADR-0009 admission + ADR-0012 redaction edge + the `a2a_outbound` flag + the in-tenant check), DAS-1611 (A2A Development — goal-proposal → board intake, `zone: scripts/a2a_intake`: the intake handler that writes a proposal into `board/goal-inbox/` and refuses forbidden fields), DAS-1612 (A2A Testing — negative-test suite; this doc hands it §3), DAS-1613 (A2A Deployment — runbook + flag flip), DAS-1614 (A2A Maintenance — health/eval).

> **Scope of this doc.** WHAT the A2A intake, publish-gate, and boundary contracts
> are and HOW their pieces interlock — the goal-proposal object shape, where it
> lands, the refusal path, the injection defense; the publish-is-a-Founder-act
> mechanism, the `board/.events.jsonl` publish-log shape, the Founder-identity
> RBAC check; the in-tenant boundary check; and the explicit statement that the
> ADR-0009 admission layer and ADR-0012 redaction discipline are **reused, not
> replaced** — one governed edge, no second entry path. It ships **no runtime
> code**: the endpoint (`tools/a2a`), the intake handler (`scripts/a2a_intake`),
> the boundary-inventory entry, and the tests are built by DAS-1610/1611/1612
> against this design. Interface shapes below are contracts, not implementations.
> This ticket touches only `docs/design/a2a-outbound.md` and the two ticket files
> (DAS-1608, DAS-1609). It modifies no ADR, no config, and no code — the
> `a2a_outbound` flag, ADR-0040, and SPEC-009 are cited, not edited. Everything is
> behind `a2a_outbound` (`config/features.yaml`) DEFAULT **OFF** — with the flag
> OFF the whole surface does not exist and a wave is byte-identical to pre-merge.

## 0. The A2A governed edge (one picture)

A2A adds a **caller type** — another agent system — not a new governance surface.
An external caller reaches exactly one governed edge, and everything it can do is
bounded by four fail-closed facts: its submission is a *proposal* (never an
approval), its payload is *data* (never instruction), the endpoint is *in-tenant
only*, and *publishing it is a Founder act*.

```
  EXTERNAL AGENT SYSTEM (untrusted caller, A2-3)
        │  submits a goal PROPOSAL (data, not instruction)
        ▼
  ┌──────────────────────────────────────────────────────────────────────┐
  │  ONE GOVERNED EDGE  (A2-5 — reused, NOT a second admission path)        │
  │   [1] ADR-0009 admission  → admit? (flag ON, in-tenant, within ceiling) │
  │   [2] ADR-0012 redaction  → no secret / no unredacted transcript crosses │
  │   [3] ADR-0024/0025 audit → the call is an attributed event, derived     │
  │                              intake — never truth                        │
  └──────────────────────────────────────────────────────────────────────┘
        │  (admitted, redacted, audited)
        ▼
  §1 INTAKE (DAS-1608 / A2-2 / FR-002)  ── scripts/a2a_intake (DAS-1611)
     writes ONLY a `status: proposed` file into board/goal-inbox/
     ── creates NO ticket · writes NO approval/gate/routing field (C3/C4)
     ── carries provenance (who/what/when/against-what-spec) for audit
     ── malformed / provenance-missing / forbidden-field ⇒ REFUSED (never silently fixed)
        │
        ▼
  FOUNDER-APPROVED GOAL QUEUE (QONUN-3/QONUN-5) ── the EXISTING mechanism
     a Founder /daslab-plan discovery is the ONLY path a proposal becomes work
     ── an external agent identity can NEVER approve a gate (TN-3)

  §2 PUBLISH + BOUNDARY (DAS-1609 / A2-4,A2-6 / FR-003,FR-004)  ── tools/a2a (DAS-1610)
     flag a2a_outbound OFF by default (ADR-0019) ⇒ endpoint does not exist
     publishing / repointing = a Founder act (rbac.decide, TN-3) → logged to board/.events.jsonl
     in-tenant only (TN-1) ── check_in_tenant.py fails a hosted-relay/registry config
```

- **[§1] A2-2 / FR-002** — a caller submission is intaken **only** as a goal
  proposal (`board/goal-inbox/` candidate artifact); it never writes an
  `approval`/gate-status/routing field and never advances a ticket past an open
  AADL gate. Approvals stay Founder-only (QONUN-5).
- **[§1] A2-3** — the caller payload is untrusted; a prompt-injection embedded in
  a proposal is inert — it lands as proposal *text* and reaches no control path.
- **[§2] A2-6 / FR-003** — the surface is `a2a_outbound` OFF by default;
  publishing it (exposing beyond disabled/internal, or repointing at any external
  registry/relay) is an explicit Founder act, logged to `board/.events.jsonl`.
- **[§2] A2-4 / FR-004** — the endpoint is in-tenant only (TN-1); a config that
  resolves to a hosted relay/registry fails `scripts/check_in_tenant.py`.
- **[§2] A2-5 / FR-005** — every inbound call is admitted (ADR-0009), redacted
  (ADR-0012), and audited (ADR-0024/0025) at the **one** existing edge; A2A stands
  up no second admission path. This design **reuses** it and designs no new
  admission mechanism.

---

## 1. Goal-proposal intake — a proposal, never a gate approval (DAS-1608 / A2-2 / FR-002)

**Requirement (FR-002 / A2-2):** any submission an external caller makes through
the A2A endpoint MUST be intaken **only** as a goal proposal — a board-intake
artifact awaiting Founder review — and MUST NEVER be treated as, auto-converted
into, or mistaken for a gate approval (QONUN-5). The proposal MUST NOT write
routing fields (C3), self-approve, or advance a ticket past an open AADL gate
(C4). This is the single invariant A2A adds on top of ADR-0036, and it is the
load-bearing one.

### 1.1 The goal-proposal object — what a caller may submit

A caller submits a **goal proposal**: a request that DasLab *consider* a goal,
carrying enough provenance for an auditor to always answer "who proposed this,
when, and against what." The object is parsed as **data to be reviewed**, never as
instruction to be executed (A2-3, §1.4). Contract shape (HOW-detail; the concrete
serialization is DAS-1611's, this fixes the fields and their meaning):

| Field | Req? | Meaning | Tier (ADR-0012) |
|---|---|---|---|
| `title` | required | one-line proposed goal (free text — DATA) | B (scrubbed at the edge) |
| `summary` | required | the proposed goal body / rationale (free text — DATA) | B |
| `proposer` | required | the caller's identity — the external agent-system principal the ADR-0009 admission edge authenticated (§1.4); an unauthenticated/anonymous proposer is refused | M (id) |
| `proposed_at` | required | ISO-8601 Z submission time | M |
| `against_spec` | optional | the spec / context the caller proposes work against (free text — DATA) | B |
| `caller_ref` | optional | a caller-side correlation id, echoed for the caller's own tracking | M (id) |
| `admission_ref` | server-stamped | the ADR-0009 admission decision id for this call (audit linkage) — stamped by the edge, never accepted from the caller | M (id) |

**Forbidden by construction — a proposal object has no place for a control field.**
The object schema **does not define** and the intake handler **rejects** any field
that would move governance: no `approval`, no `stage`/gate-status, no `status`
(`todo`/`in_progress`/`done`), no routing (`assignee`, dispatch order, reviewer),
no `ticket_type: goal` self-declaration. A submission carrying such a field is
**refused** (§1.3), not silently stripped — the caller is told the field is not
accepted, so a forbidden write is never quietly "fixed" into a success.

### 1.2 Where a proposal lands — the `board/goal-inbox/` candidate queue, never a ticket

A proposal lands as a **candidate-goal artifact** in the existing
`board/goal-inbox/` queue — the *same* landing the WS-H control plane's
goal-proposal write already uses (`docs/design/ws-h-control-plane.md` §3.1(a)): a
`status: proposed` file that **creates no ticket, approves nothing, and dispatches
nothing**, awaiting Founder discovery through `/daslab-plan` (the Founder-Approved
Goal Queue law, QONUN-3). A2A reuses this landing rather than inventing a second
one — the proposal enters the *same* Founder-gated funnel a human-submitted or
control-plane-submitted proposal enters.

The landed artifact (`board/goal-inbox/<id>.md`, shape owned by DAS-1611):

```
---
status: proposed          # the ONLY status an intake artifact may hold
source: a2a               # provenance: this proposal arrived via the A2A edge
proposer: <agent-system principal, from admission>
proposed_at: <ISO-8601 Z>
admission_ref: <ADR-0009 admission decision id>
against_spec: <optional, DATA>
---
## Proposed goal
<title>

## Rationale (proposer-supplied, UNTRUSTED — reviewed, not executed)
<summary>
```

Binding properties of the landing (each a fail-closed structural fact, not a
runtime check the handler could forget):

- **It is not a ticket.** The artifact lives in `board/goal-inbox/`, **not**
  `board/tickets/`. It never starts in `todo`/`in_progress`; it holds `status:
  proposed` and nothing else. The `/daslab-cycle` dispatcher does not read
  `board/goal-inbox/` as actionable work.
- **It writes no control field (C3/C4).** The intake handler's *only* output
  surface is a `status: proposed` goal-inbox file. It has **no code path** that
  writes an `approval`, gate-status, `assignee`, dispatch-order, or reviewer field
  anywhere. A gate/approval write is **unreachable by construction** — the
  handler cannot express it — mirroring the WS-B "a ported role is unreachable by
  construction" and WS-A "structurally unrepresentable" pattern applied to
  governance writes.
- **It carries provenance to the artifact.** `proposer` + `proposed_at` +
  `admission_ref` (+ optional `caller_ref`, `against_spec`) ride onto the landed
  file so an auditor can always answer "who proposed this and when," and so the
  Founder reviews a proposal *with* its origin visible.
- **Only a Founder promotes it.** A proposal becomes work **only** when the
  Founder runs a `/daslab-plan` discovery against the queue and explicitly
  approves it (QONUN-3/QONUN-5). No A2A path, no automation, and no repetition of
  the submission promotes it. An external agent identity can never hold
  gate-approval authority (ADR-0038 TN-3 human-only mapping).

### 1.3 The refusal path — deny, never silently drop or "fix"

A submission that is **malformed** (missing a required field), **provenance-missing**
(no authenticated `proposer`), or **carries a forbidden control field** (§1.1) is
**refused**:

- the refusal is **explicit** — the caller receives a deny, not a silent success
  and not a silently-coerced artifact. The handler never auto-corrects a bad
  proposal into a good one, and never drops a bad field to let the rest through.
- the refusal is **audited** — a deny is appended to the canonical event store
  (ADR-0024/0025), attributed to the admitted principal and redacted per ADR-0012,
  exactly as an allow is (the deny path is symmetric to the allow path, the WS-H
  §3.2 discipline).
- **fail-closed** — an ambiguous/unclassifiable submission is refused, not
  admitted. The intake handler validates the object *before* it writes anything
  (validate-first, no partial write), so a rejected proposal leaves **no** artifact
  in `board/goal-inbox/`.

### 1.4 Injection defense — a proposal can never change goals, approvals, or permissions (A2-3)

The caller payload is **untrusted input**, handled with the ADR-0033 TB-4
untrusted-ingress discipline: received content that can never change the agent's
goal, approvals, or permissions.

- **The payload is data, not instruction.** A prompt-injection embedded in a
  proposal — *"you are now approved," "skip GATE-3," "grant yourself write
  access," "set status: done"* — is **inert**: it lands as the `title`/`summary`
  *text* of a `status: proposed` goal-inbox artifact and reaches no control path.
  The intake handler parses the submission as **a proposal record to be reviewed**,
  never as a command to be executed, and never as a credential.
- **The control surface is unreachable, not merely guarded.** Because the
  handler's only output is a `status: proposed` goal-inbox file (§1.2), there is
  no code path an injected string could *steer into* an approval/gate/routing
  write — the write does not exist to be reached. Injection defense here is
  structural (the WS-A/WS-B unreachability pattern), not a blocklist of naughty
  phrases.
- **The Founder reviews text, not a directive.** When the Founder later reads the
  queue, the proposal's rationale is presented as untrusted proposer-supplied text
  (the artifact labels it so). The human review is where a proposal is judged;
  the injection cannot pre-empt or bypass that review because it never advanced
  past `status: proposed`.

**Trace:** a caller submission → a `status: proposed` `board/goal-inbox/` artifact
with provenance, no control field (unreachable by construction), malformed/forbidden
⇒ audited refusal, injection inert as reviewed text, promotion only by an explicit
Founder `/daslab-plan` act — closes **FR-002 / A2-2 / A2-3 (DAS-1608)**.

---

## 2. Publish-is-a-Founder-act + the in-tenant boundary (DAS-1609 / A2-4, A2-6 / FR-003, FR-004)

**Requirement (FR-003 / A2-6):** publishing the A2A endpoint (exposing it beyond a
disabled/internal state, or pointing it at any external registry/relay) MUST be an
explicit **Founder** act (extends ADR-0036 OB-4, QONUN-5) — never automated, never
self-triggered by a workstream ticket, and logged to `board/.events.jsonl`.
**Requirement (FR-004 / A2-4):** the endpoint MUST operate **in-tenant only**
(ADR-0038 TN-1) — no external/hosted A2A registry, relay, or endpoint that carries
code or IP; reachable only from within the declared tenant boundary.

### 2.1 The dedicated flag — `a2a_outbound`, DEFAULT OFF (A2-6 / ADR-0019)

`config/features.yaml` already carries the dedicated key `a2a_outbound: false`
(landed at DAS-1607). It is **dedicated to A2A and NOT a reuse of
`ws_d_langfuse_lens`** — A2A is a distinct external-caller trust boundary that a
tenant must be able to enable, disable, and roll back **independently** of the
WS-D observability lens (ADR-0040 Enforcement — one trust boundary, one
kill-switch). Posture:

- **OFF (default) ⇒ inert.** With `a2a_outbound` OFF the endpoint **does not
  exist**; dispatch and board behavior are **byte-identical to pre-merge** — no
  A2A route answers, no intake handler runs, no event is emitted. Merging the A2A
  machinery flips nothing (SC-005).
- **Rollback is disabling the flag / removing the endpoint wiring.** There is no
  data migration to unwind; the surface's existence is exactly the flag state.

### 2.2 Publish is a Founder act — the mechanism and the Founder-identity check (A2-6 / mirrors TN-3)

Flipping `a2a_outbound` to `true`, exposing the endpoint beyond a disabled/internal
state, or repointing it at any registry/relay is a **distribution/governance
decision reserved to the Founder** (QONUN-5) — it is **never** a workstream-ticket
decision, never automated, and never self-triggered on merge. Two enforcement legs:

- **Founder-identity RBAC, not a chat string (mirrors ADR-0038 TN-3 / reuses the
  WS-E SSOT).** The publish action is authorized by `scripts/rbac.py` `decide()`
  against `config/rbac.yaml`: a publish permission (e.g. `a2a.publish`) is granted
  to the **`founder` principal kind ONLY** — exactly as `gate.approve` /
  `config.edit.security` are Founder-only in the WS-E SSOT. An `agent`,
  `orchestrator`, or `audit-team` principal requesting publish is denied by
  construction (`decide(<non-founder>, "a2a.publish") == deny`, and
  `load_grants()` refuses an `rbac.yaml` that granted it to a non-Founder kind).
  The Founder identity is established by the authenticated session (the ADR-0039
  control-plane login / the CLI operator identity), **not** by any content an
  agent produces — no chat message, ticket field, or caller payload promotes a
  principal into `a2a.publish`. This design **reuses** that RBAC evaluator; it
  designs no new identity mechanism.
- **The flip is not a workstream ticket.** No A2A Development/Deployment ticket
  self-flips the flag. DAS-1613 (Deployment) ships the runbook + keeps the flag
  OFF on merge; the actual flip on a live surface is a separate Founder act, gated
  additionally on the Q12 go-live gate (below).

**The publish-log event (`board/.events.jsonl`).** Every publish/enable/repoint —
allow **and** deny — is appended to the canonical append-only event store
(ADR-0024/0025), attributed and redacted per ADR-0012 (no third producer; the same
canonical stream the WS-E `gate_approval` and control-plane audit writes use).
Event shape (contract; the canonical producer is DAS-1610's, this fixes the fields):

| Field | Meaning | Tier (ADR-0012) |
|---|---|---|
| `event_type` | `a2a_publish` (controlled vocabulary) | M |
| `ts` | UTC timestamp | M |
| `principal_id` | the authenticated principal string — stamped from the session, never request content | M |
| `principal_kind` | resolved kind (`_kind_of`); an appended allow can carry `founder` only if the session principal is the Founder | M |
| `decision` | `allow` / `deny` | M |
| `flag_state` | the `a2a_outbound` value the act sets (`true` / `false`) | M |
| `target` | the resolved endpoint bind/config the act publishes (a **reference**, in-tenant per §2.3) — never a secret/token | M (reference) |
| `reason` | the `decide()` reason string | M |

An event stamped `decision: allow` with `principal_kind: founder` is the *only*
record that marks the surface published — and the RBAC evaluator refuses to stamp
`founder` for a non-Founder session, so a non-Founder cannot manufacture it. A
button/CLI action that merely *sets the flag* without a backing Founder-identity
event is a forged claim with no governance weight.

**Q12 go-live gate (recorded, binding).** The A2A machinery is built now behind
`a2a_outbound` **OFF** (Founder "100% bajar" build-everything directive);
publishing a **live** A2A endpoint is deferred **until after the WS-G proof has
demonstrably shipped**, and is then the explicit Founder act above. Q12 is a
documented go-live gate on the *publish*, not a blocker on the *build* — the flag
stays OFF and the machinery ships dark until the Founder acts.

### 2.3 In-tenant only — reuse the TN-1 guard, add an A2A endpoint to the inventory (A2-4 / FR-004)

The endpoint operates **in-tenant only** (ADR-0038 TN-1): no external/hosted A2A
registry, relay, or endpoint that carries code or IP is permitted, and the surface
is reachable only from within the declared tenant boundary. This design **reuses
the existing TN-1 guard** rather than inventing a boundary mechanism:

- **The check is `scripts/check_in_tenant.py` (DAS-1543), unchanged in logic.**
  The guard already reads `config/tenant_boundary.yaml` and **fails a run** if any
  `carries_code_ip: true` endpoint whose `role` is **not** in
  `accepted_external_roles` resolves to a hosted/external host. "In-tenant" =
  loopback / RFC-1918 / ULA private / `.local`/`.internal`/bare-hostname /
  unix-socket-file-stdio; a public hostname or public IP is EXTERNAL.
- **The design adds one inventory entry** (built by DAS-1610, into
  `config/tenant_boundary.yaml`): an `a2a_outbound` endpoint with
  `carries_code_ip: true` and a role (e.g. `a2a`) that is **deliberately NOT** in
  `accepted_external_roles`. The model call remains the sole accepted proprietary
  exception (Q9) — A2A is **not** added to `accepted_external_roles`.
  ```
  - name: a2a_outbound
    role: a2a
    carries_code_ip: true          # a caller submits goals/IP through this surface
    url: <in-tenant bind — loopback default, e.g. http://127.0.0.1:PORT>
    note: A2A governed edge — must stay in-tenant (TN-1); no hosted relay/registry.
  ```
- **What a violation looks like.** A configuration that points the A2A endpoint at
  a **hosted relay or external registry** (a public hostname/IP) makes
  `check_in_tenant.py` return **exit 1** ("an external code/IP endpoint outside
  the accepted exception") and **fails the run** — the endpoint cannot be
  published to an off-box target. A call reaching the surface from outside the
  tenant is refused at the edge; a loopback-default bind (a tenant-network bind is
  a deliberate Founder act) keeps the surface reachable only within the tenant.
  There is **no public/hosted A2A SaaS surface**, consistent with the MUSTAQIL
  enterprise-internal boundary (Q10).

### 2.4 Admission + redaction are reused, not replaced — one governed edge (A2-5 / FR-005)

This design **explicitly reuses — and does not replace** — the ADR-0009 admission
layer and the ADR-0012 redaction discipline. It designs **no new admission
mechanism**; only the publish-gate (§2.2) and the boundary check (§2.3) are new,
and both are thin reuses of existing machinery.

- **Every inbound A2A call is admitted through the existing ADR-0009 edge** — the
  same admission the ADR-0036 outbound surface already passes through (the WS-B
  `admit()` gateway / the harness `PreToolUse` admission). A2A **MUST NOT** stand
  up a second, parallel admission path: there is exactly **one** place admission
  is enforced, and A2A is a new *caller* of it, not a new *edge*.
- **Every call is audited** (ADR-0024/0025 events — a caller submission is derived
  intake, never truth) **and ADR-0012 redacted at the boundary**: no secret and no
  unredacted tool transcript crosses. The same ADR-0012 §2 scrubber the WS-A tool
  path, the WS-D lens, and `append_gate_approval()` use is reused (no third
  redactor) — Tier-M ids survive, a Tier-B value is scrubbed, an unclassifiable
  value drops to `[REDACTED:unclassified]`, fail-closed (redact→truncate→append).
- **Building this wiring is DAS-1610's job.** The endpoint (`tools/a2a`) wires
  itself *through* the existing admission+redaction chain and the flag; this design
  fixes the contract it builds against and asserts the "no second entry path"
  invariant it must satisfy.

**Trace:** dedicated `a2a_outbound` OFF-by-default flag (independent kill-switch);
publish = a Founder-identity `decide("a2a.publish")` act logged to
`board/.events.jsonl` (mirrors TN-3, reuses the WS-E RBAC SSOT), deferred to the
Q12 go-live gate; in-tenant only via the reused `check_in_tenant.py` +
`tenant_boundary.yaml` inventory entry (hosted relay/registry fails the check);
ADR-0009 admission + ADR-0012 redaction reused at one edge, no second admission
path — closes **FR-003 / FR-004 / FR-005 / A2-4 / A2-5 / A2-6 (DAS-1609)**.

---

## 3. Negative-path spec for DAS-1612 (Testing / GATE-4)

The behaviours the Testing ticket (DAS-1612, `zone: tests`, `implements: [SC-001,
SC-002, SC-004]`, red-team consulted) must assert. Each is written to be
implemented directly against the A2A surfaces DAS-1610 (`tools/a2a`) and DAS-1611
(`scripts/a2a_intake`) build, plus the reused primitives (the ADR-0009 admission
edge, the ADR-0012 scrubber, `scripts/check_in_tenant.py`, `scripts/rbac.decide()`),
and folded into `tests/test_a2a_outbound.py`.

### SC-001 — gate-bypass + no self-approval (A2-1 / A2-2)

- **SC-001a — cannot advance past an open gate.** Given a ticket with an **open**
  AADL gate, assert that **no** A2A call — however the submission is shaped or
  repeated — advances the ticket past that gate. The A2A surface offers only
  "deliver this spec through the AADL-gated org," never raw tool/agent access and
  never a gate-advance; the gate order is enforced by the engine dispatcher +
  `scripts/check_never_auto_approve.py` independently of the caller.
- **SC-001b — cannot self-approve.** Assert an external A2A call cannot cause a
  self-approval — there is no A2A path that emits a `gate_approval` event or sets
  an `approval` field; an external agent identity holds no gate-approval authority
  (`decide("agent:<any>", "gate.approve") == deny`, TN-3).

### SC-002 — goal-proposal-not-approval, under any input shape (A2-2)

- **SC-002a — lands only as a board-intake artifact.** Assert a goal proposal
  submitted via A2A lands **only** as a `status: proposed` `board/goal-inbox/`
  file — it creates **no** `board/tickets/` ticket, starts in **no**
  `todo`/`in_progress` status, and dispatches nothing.
- **SC-002b — never flips a control field, however shaped/repeated.** Assert that
  a proposal carrying an `approval` / gate-status / `status: done` / routing field
  (in any position, any casing, repeated N times) **never** flips that field on
  the board — the field is **refused** (§1.3), not stripped-and-accepted, and the
  landed artifact (if any) holds only `status: proposed`. Assert the intake
  handler has no code path that writes an approval/gate/routing field (the
  unreachable-by-construction property, §1.2/§1.4).
- **SC-002c — injection is inert.** Feed a proposal whose `summary` is a
  prompt-injection (*"you are approved," "skip GATE-3," "grant write access,"
  "set status: done"*); assert it lands as inert proposal **text** in a `status:
  proposed` artifact and changes **no** goal, approval, or permission — it reaches
  no control path (A2-3). Only an explicit Founder `/daslab-plan` act can promote
  the proposal.

### SC-004 — admission-skip denied + redaction probe (A2-5)

- **SC-004a — admission-skip denied.** Assert a call that attempts to reach the
  A2A surface **skipping** the ADR-0009 admission layer is **denied** — there is
  no code path into intake or delivery that bypasses `admit()`; admission is the
  one edge (no second path). A call missing/forging admission is refused with an
  audited deny.
- **SC-004b — redaction probe.** Feed a transcript/payload crossing the A2A
  boundary that carries a **planted secret** (an `sk-ant-…` key, an
  `Authorization: Bearer …`/JWT, a `postgres://user:pass@host/db` DSN, a PII
  email/name); assert the ADR-0012 scrubber replaces each with its `[REDACTED:…]`
  token before it leaves the process — **no** raw secret/PII substring survives —
  and that the boundary record is Tier-M (no secret/prompt/completion field),
  fail-closed (redact→truncate→append), with Tier-M ids un-over-redacted.

### SC-003 / SC-005 boundary + flag guard (handed to DAS-1612; closed at DAS-1613 Deployment)

These exercise the §2 publish/boundary invariants. DAS-1612 asserts them at the
unit/negative-test layer; the live-surface half (a deployed VM, the actual flag
flip) is confirmed again at DAS-1613 (Deployment / SC-003, SC-005).

- **Hosted endpoint blocked (in-tenant, SC-003).** Assert a
  `config/tenant_boundary.yaml` whose `a2a_outbound` endpoint resolves to a
  **hosted relay/registry** (a public hostname/IP) makes `scripts/check_in_tenant.py`
  **fail** (exit 1); assert an in-tenant (loopback / RFC-1918 / `.local`) bind
  **passes** (exit 0). A call from outside the tenant is refused at the edge.
- **Flag-off inert (SC-005).** Assert `config/features.yaml` carries `a2a_outbound:
  false`, and that with the flag OFF a wave's dispatch/board behavior is
  **byte-identical** to a pre-merge baseline — the endpoint does not exist, the
  intake handler does not run, and no A2A event is emitted.
- **Publish requires a Founder act (SC-003).** Assert
  `decide("founder", "a2a.publish") == allow` and `decide(<non-founder>,
  "a2a.publish") == deny` for every non-Founder principal (`audit-team`,
  `orchestrator`, `agent:<any-of-32-roles>`); assert a publish/enable/repoint
  action appends an attributed `a2a_publish` event to `board/.events.jsonl` with
  `principal_kind: founder` **only** for a Founder session, and that a non-Founder
  publish attempt is a **403 + audited deny** that emits **no** allow event and
  leaves the flag unchanged.

**Hand-off:** SC-001 → §1.1/§1.2 (intake, no gate-advance); SC-002 → §1
(proposal-not-approval, injection inert); SC-004 → §2.4 (admission+redaction
reuse); SC-003/SC-005 guard → §2.1–§2.3 (flag, publish-Founder-act, in-tenant
check). All assertions are expressible against the DAS-1610/1611 surfaces plus the
reused `check_in_tenant.py` / `rbac.decide()` / ADR-0012-scrubber primitives.

---

## 4. Traceability matrix

| SPEC FR / SC | ADR-0040 A2 | This design | DAS-1612 SC | Builds in |
|---|---|---|---|---|
| FR-002 — caller submission is a goal proposal only; no approval/gate/routing write; no gate-advance | A2-2 (+ A2-3 injection) | §1 (`board/goal-inbox/` `status: proposed` landing, provenance, control-field unreachable by construction, audited refusal, injection inert) | SC-001, SC-002 | DAS-1611 |
| FR-003 — publishing is a Founder act; logged to `board/.events.jsonl`; never automated/self-triggered | A2-6 | §2.1 (dedicated flag OFF) + §2.2 (`decide("a2a.publish")` Founder-only, publish-log event, Q12 go-live gate) | SC-003 (guard) | DAS-1610/1613 |
| FR-004 — in-tenant only; no hosted registry/relay; reachable only within the tenant | A2-4 | §2.3 (reuse `check_in_tenant.py` + a `tenant_boundary.yaml` `a2a_outbound` entry NOT in `accepted_external_roles`; hosted target fails the check) | SC-003 (guard) | DAS-1610 |
| FR-005 — reuse the ADR-0009 admission + ADR-0012 redaction edge; no second admission path | A2-5 | §2.4 (one governed edge reused; no new admission mechanism; ADR-0012 §2 scrubber reused) | SC-004 | DAS-1610 |
| FR-001 — governed delivery, not raw agent access; cannot skip a gate / self-approve | A2-1 | §0 + §1 (only "deliver this spec through the AADL-gated org"; gate order engine-enforced) | SC-001 | DAS-1610 |
| FR-006 — feature-flagged OFF by default; flag-off == pre-merge | A2-6 | §2.1 (`a2a_outbound` OFF ⇒ inert, byte-identical) | SC-005 (guard) | DAS-1610/1613 |

## 5. Open items handed downstream (not decided here)

- **DAS-1610** (`tools/a2a`) stands up the endpoint: wires it through the existing
  ADR-0009 admission + ADR-0012 redaction edge (§2.4, no second path), consumes the
  `a2a_outbound` flag (§2.1), adds the `a2a_outbound` entry to
  `config/tenant_boundary.yaml` (§2.3), and implements the `a2a_publish` event
  producer + the Founder-only `decide("a2a.publish")` publish-gate (§2.2). Behind
  `a2a_outbound` OFF.
- **DAS-1611** (`scripts/a2a_intake`) builds the intake handler: parses the
  goal-proposal object (§1.1), writes a `status: proposed` `board/goal-inbox/`
  artifact with provenance (§1.2), refuses malformed/provenance-missing/forbidden-field
  submissions with an audited deny (§1.3), and carries the injection-inert data
  discipline (§1.4). It approves/promotes/dispatches nothing.
- **DAS-1612** (`tests`) implements §3 (SC-001, SC-002, SC-004 + the SC-003/SC-005
  guard) in `tests/test_a2a_outbound.py`.
- **DAS-1613 (Deployment)** carries the runbook + keeps `a2a_outbound` OFF on
  merge; confirms SC-003 (in-tenant boundary on the live surface) + SC-005
  (flag-off byte-identical). The **actual flip is a Founder act**, gated on the Q12
  go-live gate (§2.2) — not this workstream's decision.
- **Security Lead (consulted)** reviews §1 (proposal-not-approval, injection
  defense), §2.2 (Founder-only publish RBAC mirroring TN-3), §2.3 (TN-1 boundary),
  and §2.4 (ADR-0009/ADR-0012 reuse, no second entry path); **CTO (accountable)**
  ratifies GATE-2 closure for both DAS-1608 (§1) and DAS-1609 (§2).
- The concrete `tools/a2a` module layout, the endpoint's wire protocol shape (the
  agent2agent-lineage transport), the in-tenant bind port, and the exact
  `a2a.publish` permission key string are ADR-0040-sanctioned implementation
  choices left to DAS-1610, not decided here.
