---
id: DAS-1545
title: WS-A Planning — ratify ADR-0033, review SPEC-002, land the WS-A feature key OFF
status: done
assignee: cto
author: ceo
dept: engineering
priority: p1
parent: DAS-1544
goal: mustaqil-ws-a-reach
spec: 002-mustaqil-ws-a-reach
implements: [FR-001, FR-004]
labels: [governance, security]
zone: docs/adr
depends_on: [DAS-1543]
created: 2026-07-23
updated: 2026-07-24
---

## Description

**AADL Stage 1 — Planning (closes GATE-1 for WS-A).**

- Ratify **ADR-0033** (currently `Proposed`) → `Accepted` after CTO sign-off (RACI
  3.1/3.6); Security Lead consulted on tool admission + ADR-0012 redaction.
- Review `docs/specs/002-mustaqil-ws-a-reach/SPEC.md` (FR-001…FR-006, SC-001…SC-004);
  resolve any `[NEEDS CLARIFICATION]`; mark SPEC Status `reviewed`.
- Land the WS-A feature key in `config/features.yaml` DEFAULT **OFF** (from the
  DAS-1543 scaffold) — the flag that guards the tool bridge (TB-5).

No tool is built in this stage — this fixes the contract the WS-A code builds against.

## Acceptance criteria
- [x] ADR-0033 Status flipped to `Accepted` with the CTO sign-off recorded; `docs/adr/README.md` consistent.
- [x] SPEC-002 reviewed (Status `reviewed`), no unresolved clarification markers.
- [x] WS-A feature key present in `config/features.yaml`, value `false`, with a consumer/flip comment (confirmed from DAS-1543 — not re-added).
- [x] `check_spec_consistency`/`check_links`/`board_lint` green. (Doc/governance ticket, LOCAL-ONLY — no PR/CI exists; exempt from the merged-PR done-gate, accepted on local green.)

## Log
### 2026-07-23 — CEO
Created by /daslab-plan (WS-A Planning). Ratifies ADR-0033; reviews SPEC-002.

### 2026-07-24 — CTO
**AADL Stage 1 — Planning (GATE-1) CLOSED for WS-A REACH.**

1. **ADR-0033 ratified → Accepted.** Judged TB-1…TB-5 sound against ADR-0009
   (MCP edge = admission, not transport), ADR-0012 (tool events classified +
   redacted — TB-3), C1/C2 (tools are substrate; board + governance canonical —
   Law-check section), and Founder Q5 (deny-all + domain allow-list egress).
   One precision fix applied before sign-off: TB-4 previously said browser
   "egress is treated as untrusted input," conflating untrusted *ingress*
   (fetched content / injection defense) with *egress-destination* control. It
   now binds Q5 explicitly — (a) ingress = untrusted content that can't change
   goal/approvals/permissions; (b) egress = deny-all except an explicit domain
   allow-list — cleanly tracing SPEC-002 FR-006 (ingress) and FR-005 (egress).
   Not a send-back: a one-clause ratifier tightening aligning the ADR to an
   already-decided, already-consulted Q5 answer (also encoded in ADR-0038 TN-5),
   no posture change. Status line + Enforcement bullet carry the dated CTO
   sign-off (matching ADR-0041 style); `docs/adr/README.md` row 0033 → Accepted.
   Security Lead consult (tool admission + ADR-0012 redaction) adequately
   captured in the header, Deciders line, and Enforcement bullet.
2. **SPEC-002 reviewed → Status `reviewed`.** FR-001…FR-006 + SC-001…SC-004 are
   coherent, testable, and trace cleanly (FR-001→TB-1, FR-002→TB-2, FR-003→TB-3,
   FR-004→TB-5, FR-005→TB-4/Q5 egress, FR-006→TB-4/Q5 ingress; SC-001→FR-002/003,
   SC-002→FR-005/003, SC-003→FR-004/TB-5, SC-004→diagnostics/board_lint). No
   `[NEEDS CLARIFICATION]` markers present — none to resolve.
3. **WS-A feature key confirmed.** `ws_a_tool_bridge: false` already present in
   `config/features.yaml` (landed by DAS-1543) with consumer/flip comment
   (tools/ bridge + check_in_tenant TN-1; flip when deny-all + allow-list egress
   Q5 live). Not re-added / not edited — confirmed only.

Validators (re-run by CTO, all exit 0): `check_links` OK; `check_spec_consistency`
OK (2 SPECs, structure + refs consistent); `board_lint` OK (110 tickets, 0
violations — only the pre-existing unrelated DAS-1507 body-status WARN).

LOCAL-ONLY: no branch/commit/push/PR. Doc/governance ticket — no PR/CI exists,
exempt from the merged-PR done-gate, accepted on local green. GATE-1 closed →
unblocks the WS-A Design ticket DAS-1546. No defect requiring send-back, no
escalation.
