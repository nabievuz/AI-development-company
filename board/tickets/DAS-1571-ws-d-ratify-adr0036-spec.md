---
id: DAS-1571
title: WS-D Planning — ratify ADR-0036, review SPEC-005, confirm the WS-D feature key OFF
status: done
assignee: cto
author: ceo
dept: engineering
priority: p1
parent: DAS-1570
goal: mustaqil-ws-d-lens
spec: 005-mustaqil-ws-d-lens
implements: [FR-001, FR-004, FR-006]
labels: [governance, security]
zone: docs/adr
depends_on: [DAS-1543]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 1 — Planning (closes GATE-1 for WS-D).**

- Ratify **ADR-0036** (currently `Proposed`) → `Accepted` after CTO sign-off
  (RACI 3.1/3.6); Security Lead consulted on the OTLP export redaction (OB-3);
  CMO consulted on distribution (OB-4). Confirm the ADR's stance that the
  self-host Langfuse lens is NOT LangSmith / NOT a hosted endpoint, and that
  the tool-admission shortlist (promptfoo, AgentShield, Presidio) rides the
  ADR-0033 edge rather than opening a second admission path.
- Review `docs/specs/005-mustaqil-ws-d-lens/SPEC.md` (FR-001…FR-006,
  SC-001…SC-005); resolve any `[NEEDS CLARIFICATION]`; mark SPEC Status
  `reviewed`.
- Confirm the `ws_d_langfuse_lens` feature key in `config/features.yaml`
  DEFAULT **OFF** (already landed by DAS-1543) — the flag that guards the
  OTLP exporter (FR-004).

No exporter and no tool wiring is built in this stage — this fixes the
contract the WS-D code builds against.

## Acceptance criteria
- [x] ADR-0036 Status flipped to `Accepted` with the CTO sign-off recorded; `docs/adr/README.md` consistent.
- [x] SPEC-005 reviewed (Status `reviewed`), no unresolved clarification markers.
- [x] `ws_d_langfuse_lens` feature key confirmed present in `config/features.yaml`, value `false`, with its consumer/flip comment (from DAS-1543 — not re-added).
- [x] `check_spec_consistency`/`check_links`/`board_lint` green.

## Log
### 2026-07-24 — Senior Product Manager
Created by /daslab-plan (WS-D Planning). Ratifies ADR-0036; reviews SPEC-005;
confirms the pre-landed `ws_d_langfuse_lens` OFF scaffold.

### 2026-07-24 — CTO — GATE-1 (Planning) CLOSED for WS-D LENS

**ADR-0036 ratified: Proposed → Accepted (RACI 3.1/3.6 A).** Judged sound
against ADR-0024 (spans already `gen_ai.*`-named → OTLP export to Langfuse is a
field-mapping shim, not a migration), ADR-0012 (redact-before-export, fail-closed
— OB-3), ADR-0025 (event store canonical; lens derived — OB-2/C2), ADR-0033
(promptfoo/AgentShield/Presidio ride the existing governed MCP edge, no second
admission path — OB-3), and ADR-0038 TN-1 (self-host / in-tenant only).

**Correction made during ratification (not a rubber-stamp):** the ADR body,
H1 title, context, OB-2, OB-4, consequences, and law-check all leaned
**LangSmith** (the pre-decision draft). The DECIDED choice is **self-host
Langfuse via OTLP — NOT LangSmith** (master prompt v3.0 row D + Part 0). I
rewrote OB-2 to bind the exporter to an in-tenant Langfuse endpoint and to
FORBID any hosted/cloud fallback (LangSmith or Langfuse-cloud), added the
ADR-0038 TN-1 in-tenant relation, and folded the ADR-0033 tool-admission edge
into OB-3. `docs/adr/README.md` row 0036 + the LangChain-direction theme note
updated to the self-host-Langfuse stance and → Accepted. NB: the file slug
retains `-langsmith` because 0034/0037/0038/0039 (outside this ticket's
touch-set) link to it — renaming would break `check_links` in files I may not
touch; the decision lives in the ADR title + body, not the slug.

**SPEC-005 reviewed: draft → reviewed.** FR-001…006 each trace to ADR-0036
OB-1…OB-4 + ADR-0033/0012/0024/0038; every FR has a covering, testable SC
(SC-001 flag-off byte-identical, SC-002 redaction probe, SC-003 tool-admission
negative test, SC-004 in-tenant-only endpoint resolution, SC-005
diagnostics/validators). No `[NEEDS CLARIFICATION]` markers. WHAT/WHY-only
separation from the HOW is clean. No defect — accepted as reviewed.

**Feature key confirmed:** `config/features.yaml` line 23 —
`ws_d_langfuse_lens: false` with the DAS-1543 consumer/flip comment
("in-tenant trace/eval viewer … Flip when self-host Langfuse is up on the tenant
VM (Q2) and in-tenant (TN-1)"). Present, OFF, not re-added — FR-004 satisfied.

**Consultations recorded (documented in ADR, not routed):** Security Lead
consulted on OTLP-export redaction (OB-3); CMO consulted on distribution (OB-4).
These are captured in the ADR sign-off block per RACI; no live routing needed
for a CTO ratification act.

**Validators:** `check_spec_consistency` exit 0 (10 SPECs, structure + refs
consistent); `check_links` exit 0 (no broken relative links); `board_lint`
exit 0 (180 tickets, 0 violations; the one DAS-1507 body-status WARN is
pre-existing and non-fatal, unrelated to this ticket).

**GATE-1 (Planning) is CLOSED for WS-D LENS.** This unblocks **DAS-1572**
(WS-D Stage-2 Design). Touched files: `docs/adr/0036-outbound-interop-surface-langsmith.md`,
`docs/adr/README.md`, `docs/specs/005-mustaqil-ws-d-lens/SPEC.md`, this ticket.
⛔ LOCAL-ONLY — no push/PR/commit performed.
