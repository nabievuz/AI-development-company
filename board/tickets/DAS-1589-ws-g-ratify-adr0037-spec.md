---
id: DAS-1589
title: WS-G Planning — author and ratify ADR-0037, review SPEC-007, fix the proof scope
status: todo
assignee: cto
author: ceo
dept: engineering
priority: p1
parent: DAS-1588
goal: mustaqil-ws-g-proof
spec: 007-mustaqil-ws-g-proof
implements: [FR-001, FR-002]
labels: [governance]
zone: docs/adr
depends_on: [DAS-1543]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 1 — Planning (closes GATE-1 for WS-G).**

- Ratify **ADR-0037** (currently `Proposed`) → `Accepted` after CTO sign-off
  (RACI 3.1/3.6); CEO + Founder consulted (this fixes the org completion contract).
- Review `docs/specs/007-mustaqil-ws-g-proof/SPEC.md` (FR-001…FR-008, SC-001…SC-005);
  resolve any `[NEEDS CLARIFICATION]`; mark SPEC Status `reviewed`.
- **Fix the proof scope** (FR-001): record that the Founder-fixed proof = the **WS-H
  dashboard slice** (Q1, e.g. the CP-3b trigger-run), immutable for the run — no
  self-scoping; an ambiguous boundary halts at the Clarify gate (ADR-0014) + escalates.
- Confirm the WS-G feature key `ws_g_proof` in `config/features.yaml` DEFAULT **OFF**
  (landed by DAS-1543 — confirm, do not re-add).

No harness or gate is built in this stage — this fixes the contract and the scope the
WS-G code builds against. The proof PROJECT is not created here; its skeleton is
bootstrapped later by DAS-1593.

## Acceptance criteria
- [ ] ADR-0037 Status flipped to `Accepted` with the CTO sign-off recorded; `docs/adr/README.md` consistent.
- [ ] SPEC-007 reviewed (Status `reviewed`), no unresolved clarification markers.
- [ ] Proof scope recorded as Founder-fixed (Q1 WS-H slice) and immutable; the no-self-scope + Clarify-gate rule stated.
- [ ] `ws_g_proof` confirmed present in `config/features.yaml`, value `false` (confirmed from DAS-1543 — not re-added).
- [ ] `check_spec_consistency`/`check_links`/`board_lint` green. (Doc/governance ticket, LOCAL-ONLY — no PR/CI; exempt from the merged-PR done-gate, accepted on local green.)

## Log
### 2026-07-24 — Senior Product Manager
Created by /daslab-plan (WS-G Planning). Ratifies ADR-0037 (ED-1..ED-5); reviews
SPEC-007; fixes the proof scope to the Founder Q1 WS-H dashboard slice. ADR
ratification is a CTO act — assignee cto.
</content>
