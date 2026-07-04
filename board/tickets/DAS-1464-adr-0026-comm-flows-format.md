---
id: DAS-1464
title: Author ADR-0026 communication-flows format and gate-owner reconciliation
status: done
assignee: chairman
author: ceo
dept: engineering
priority: p1
parent: DAS-1463
goal: organism-ws2-loom
zone: docs/adr
created: 2026-07-03
updated: 2026-07-03  # GATE-1 sign-off
---

## Description

**What.** Author `docs/adr/0026-communication-flows.md` — a new, append-only ADR
(the highest existing is `0025`; you author `0026`) that fixes three decisions
needed before ORGANISM WS2 LOOM can encode a machine-readable
`communication-flows.yaml`:

1. **The `communication-flows.yaml` format.** Decide a directional-edge schema:
   each edge is a `(sender_role, receiver_role)` tuple carrying a `kind` ∈
   {`delegation` (down the reporting chain), `escalation` (up the chain)}.
   Roles are the canonical role keys already in `board/ROUTING.md` /
   `org/schema.daslab.yaml` (e.g. `cto`, `backend-em`, `security-lead`), so the
   flows file is a derived, validatable view of the existing org graph
   (reporting lines from `board/ROUTING.md`, escalation ladder
   `[ic, lead, cxo, founder]` from `org/schema.daslab.yaml:routing.escalation`).
   Specify the exact YAML shape (top-level key, per-edge fields, allowed enums)
   so a validator can diff it against the SSOTs.

2. **Reconcile the GATE-1 / GATE-6 owner discrepancy** (approved §9 default #1).
   The two sources disagree and MUST be reconciled without editing either in
   place:
   - `governance/policies/ai-agent-lifecycle.md` §1 (AADL RACI) is the
     **AUTHORITATIVE Accountable owner** — GATE-1 → `cpo`, GATE-6 → `coo`
     (exactly one Accountable per gate, standard RACI).
   - `org/schema.daslab.yaml:roles[*].gate_owner` is the **SIGNER SET** — the
     roles whose sign-off is collected at that gate (GATE-1 → `{founder, cpo}`;
     GATE-6 → `{cto}`). It is NOT a second "Accountable".
   Document the rule explicitly: **RACI = the single Accountable; schema
   `gate_owner` = the signer set.** State that `communication-flows.yaml` reads
   BOTH — the Accountable from AADL RACI, the signer roster from the schema — and
   that they are complementary, not conflicting. No `A↔A` claim exists once read
   this way (RACI §Conflict-resolution #3 is not triggered).

3. **Founder is an external human gate ABOVE the chairman, NOT a routing node**
   (approved §9 default #2). The founder appears as the terminal rung of the
   escalation ladder (`org/schema.daslab.yaml:routing.escalation` ends in
   `founder`) and as a GATE-1 signer, but is **not one of the 32 agent roles**
   in the fleet routing graph (`board/ROUTING.md` lists no `founder` row). Record
   that `communication-flows.yaml` therefore does NOT emit `founder` as a
   sender/receiver agent node — the founder is modeled as the human approval
   boundary the fleet escalates INTO, sitting above `chairman`.

**Why.** WS2 LOOM needs a single, unambiguous decision of record before it can
generate/validate a `communication-flows.yaml`; today the gate ownership reads
two ways and there is no written rule for whether the founder is a graph node.
This is a GATE-1 Planning artifact for the ORGANISM program.

**Extend vs. new.** NEW ADR file (`0026`) — ADRs are append-only and each new
decision takes the next free number (`docs/adr/README.md` header). Do NOT edit
`ai-agent-lifecycle.md` or `org/schema.daslab.yaml` in this ticket; ADR-0026
*interprets and reconciles* them by reference, it does not mutate them.

**Key files (paths).**
- `docs/adr/0026-communication-flows.md` — the new ADR (create).
- `docs/adr/README.md` — add the index row (`| 0026 | … | Accepted | 2026-07-03 |`)
  and extend the ORGANISM WS2 LOOM theme block.
- `governance/policies/ai-agent-lifecycle.md` §1 — cited as the Accountable SSOT.
- `org/schema.daslab.yaml` (`roles[*].gate_owner`, `routing.escalation`) — cited
  as the signer-set + escalation-ladder SSOT.
- `board/ROUTING.md` — cited as the reporting-line SSOT and the enumeration of
  the fleet role nodes (no `founder` row).
- `governance/policies/raci.md` §3.1 — ADR approval RACI (CTO is A; ratifies).
- Spec-of-record: `docs/research/ORGANISM-PROGRAM-PLAN.md`.

Per RACI §3.1 the CTO is Accountable for an ADR (ratifies); this ticket is
assigned to `cto` accordingly.

## Acceptance criteria

- [ ] `docs/adr/0026-communication-flows.md` merged, following the ADR shape
      (Context / Decision / Consequences, `Status: Accepted`, `Date: 2026-07-03`).
- [ ] `docs/adr/README.md` gains the `0026` index row AND its ORGANISM WS2 LOOM
      theme entry.
- [ ] The `communication-flows.yaml` format is specified: directional
      `(sender_role, receiver_role)` tuples with `kind` ∈ {delegation,
      escalation}, role keys drawn from the existing SSOTs, exact YAML shape +
      enums given.
- [ ] The GATE-1/GATE-6 owner reconciliation is explicit and unambiguous:
      **AADL RACI = the single Accountable** (GATE-1 cpo, GATE-6 coo);
      **schema `gate_owner` = the signer set** (GATE-1 {founder, cpo}, GATE-6
      {cto}); flows reads both.
- [ ] The founder-node decision is recorded: founder = external human gate above
      chairman, NOT one of the 32 fleet routing nodes; not emitted as a
      sender/receiver in `communication-flows.yaml`.
- [ ] `python3 scripts/diagnostics.py` (or the repo's release gate) reports
      100/100; `board_lint` passes (no `project:` field — org-engine ticket).

## Log

### 2026-07-03 — CEO
Created from ORGANISM WS2 LOOM decomposition (/daslab-plan). Spec-of-record: docs/research/ORGANISM-PROGRAM-PLAN.md.
To write precise criteria + paths, READ: docs/adr/README.md, board/ROUTING.md, org/schema.daslab.yaml, governance/policies/raci.md, governance/policies/ai-agent-lifecycle.md.
Confirmed against sources: highest existing ADR is 0025 → author 0026. AADL §1 gives Accountable owners GATE-1=cpo, GATE-6=coo; org/schema.daslab.yaml gate_owner lists GATE-1={founder,cpo} and GATE-6={cto} — these are the SIGNER SET, reconciled here as complementary to (not competing with) the single RACI Accountable. routing.escalation = [ic, lead, cxo, founder]; board/ROUTING.md has no `founder` row → founder is the human boundary above chairman, not a fleet node. RACI §3.1: CTO is A for ADRs → assignee cto.

### 2026-07-03 — CTO
Authored `docs/adr/0026-communication-flows.md` (Accepted, 2026-07-03) and added its index row + ORGANISM WS2 LOOM theme block to `docs/adr/README.md`. Three decisions of record:
1. **comm-flows format.** `governance/communication-flows.yaml` is a DERIVED, validatable view: `version` + top-level `flows:` list; each item a directional `(sender, receiver)` edge with `kind` ∈ {`delegation` (down the reporting chain), `escalation` (up it)} and a `source` provenance ∈ {`routing.reports_to`, `schema.escalation`}. `sender`/`receiver` MUST be role keys from board/ROUTING.md (`founder` forbidden). Four derivation/validation rules (role-node closure; per-reporting-line exactly-two-edges completeness; one-rung escalation-ladder consistency; no invented topology) are the contract `check_comm_flows.py` (O2-T03) enforces — undeclared route unrepresentable + diff-checkable against the SSOTs. RACI *consult* edges deferred to a future `kind` (v1 enum stays closed).
2. **GATE-1/6 owner reconciliation.** Explicit rule: **AADL RACI §1 = the single Accountable** (GATE-1 cpo, GATE-6 coo); **schema `gate_owner` = the signer set** (GATE-1 {founder, cpo}, GATE-6 {cto}) — complementary, not a second Accountable. GATE-1: cpo is Accountable AND a signer, founder signer-only. GATE-6: coo Accountable, cto recorded signer — orthogonal RACI dimensions, so no A↔A (RACI §Conflict-resolution #3 not triggered). Flows/gate readers read both lanes; no SSOT edited in place.
3. **founder node.** External human gate ABOVE chairman, terminal rung of the escalation ladder + GATE-1 signer, but NOT one of the 32 fleet routing nodes (no ROUTING.md row) → NEVER emitted as a `sender`/`receiver` in communication-flows.yaml; fleet escalation terminates at chairman/board-member (reviewer `—`).
VERIFY (full, in worktree): `python3 -m pytest -q` → 1083 passed, 1 skipped; `scripts/diagnostics.py` → 100/100; `scripts/board_lint.py` → OK 0 violations. No SSOT mutated (ai-agent-lifecycle.md / schema.daslab.yaml / ROUTING.md untouched — interpreted by reference only). Committed LOCAL to branch feat/das-1464-adr-0026-commflows (no push — strict local-only). status → in_review. Reviewer routing: CTO's manager is CEO (ROUTING.md), but the ticket `author` is `ceo` and board_lint forbids assignee==author (self-review); per the ROUTING.md rule "if the manager IS the author, escalate one level," reviewer → `chairman` (CEO's manager). RACI 3.1: CTO=A ratifier.

### 2026-07-03 — Chairman of the Board
**GATE-1 sign-off — VERDICT: PASS.** Reviewed `docs/adr/0026-communication-flows.md` + `docs/adr/README.md` against the ticket acceptance and the AADL §3 GATE-1 checklist. Every claim in the ADR was cross-checked against the live SSOTs, not taken on trust:
1. **Comm-flows format (§1).** Confirmed directional `(sender, receiver)` tuples with `kind` ∈ {`delegation` down / `escalation` up} and a `source` provenance ∈ {`routing.reports_to`, `schema.escalation`}; closed enums; role keys constrained to `board/ROUTING.md` fleet nodes (`founder` forbidden); four derivation/validation rules make the file a pure, diff-checkable function of the SSOTs (O2-T03 contract). Meets acceptance.
2. **Gate-owner reconciliation (§2).** Verified against sources: AADL §1 RACI Accountable = GATE-1 `cpo` (line 30), GATE-6 `coo` (line 35); schema `gate_owner` signer set = GATE-1 `{founder, cpo}` (schema L17–18), GATE-6 `{cto}` (cto `gate_owner` includes GATE-6, L19; coo does not). The ADR's rule — **RACI = single Accountable (authoritative); schema `gate_owner` = signer roster; complementary, not a second Accountable** — is exactly right; no `A↔A`, RACI §Conflict-resolution #3 not triggered. Flows reads both lanes.
3. **Founder node (§3).** Confirmed `board/ROUTING.md` has NO `founder` row; `chairman` and `board-member` reviewer = `—` (top of fleet chain); `schema.routing.escalation` = `[ic, lead, cxo, founder]` (L13). Founder correctly modeled as the external human gate ABOVE chairman, never emitted as a `sender`/`receiver`. Meets acceptance.
4. **No SSOT edited in place.** Verified at the git level: the ADR commit (a35c4f8) touches exactly 3 files — the ticket, the new `docs/adr/0026-*.md`, and `docs/adr/README.md`; `ai-agent-lifecycle.md` / `schema.daslab.yaml` / `ROUTING.md` untouched. Append-only ADR numbering (0025 → 0026) correct. README index row 0026 present + ORGANISM WS2 LOOM theme block added; link resolves. RACI 3.1 satisfied (CTO=A ratifier; reviewer routing to chairman correct — CEO is author, escalate one rung).
GATES (main checkout, re-run): `scripts/diagnostics.py` → **100/100**; `scripts/board_lint.py` → **0 violations** (32 tickets); `python3 -m pytest -q` → **1105 passed, 1 skipped, 0 failed**. status → done. Committed LOCAL only (no push — strict local-only).
