---
id: DAS-1589
title: WS-G Planning — author and ratify ADR-0037, review SPEC-007, fix the proof scope
status: done
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
- [x] ADR-0037 Status flipped to `Accepted` with the CTO sign-off recorded; `docs/adr/README.md` consistent.
- [x] SPEC-007 reviewed (Status `reviewed`), no unresolved clarification markers.
- [x] Proof scope recorded as Founder-fixed (Q1 WS-H slice) and immutable; the no-self-scope + Clarify-gate rule stated.
- [x] `ws_g_proof` confirmed present in `config/features.yaml`, value `false` (confirmed from DAS-1543 — not re-added).
- [x] `check_spec_consistency`/`check_links`/`board_lint` green. (Doc/governance ticket, LOCAL-ONLY — no PR/CI; exempt from the merged-PR done-gate, accepted on local green.)

## Log
### 2026-07-24 — Senior Product Manager
Created by /daslab-plan (WS-G Planning). Ratifies ADR-0037 (ED-1..ED-5); reviews
SPEC-007; fixes the proof scope to the Founder Q1 WS-H dashboard slice. ADR
ratification is a CTO act — assignee cto.

### 2026-07-24 — CTO — GATE-1 (Planning) CLOSED for WS-G PROOF
AADL Stage-1 closed. Judged the MUSTAQIL completion contract sound and RATIFIED
ADR-0037 (`Proposed` → `Accepted`, dated CTO sign-off, RACI 3.1/3.6 A;
`docs/adr/README.md` row 0037 → Accepted).

Ratification verdict — the contract holds against the two failure modes I am
accountable to foreclose:
- **No false-green:** ED-1 defines "finished" ONLY by evidence (all AADL gates
  closed, merged PR + green CI per code ticket, committed hash-chained
  attestation per ADR-0031/0032, diagnostics 100/100 on a clean tree, golden
  eval + anti-gaming probe). ADR-0020 is enforced — an unmeasured dimension is
  SKIPPED, never counted green. SPEC-007 FR-004 (evidence gate rejects a
  false-green) + FR-003 (anti-gaming probe) + SC-004 (a "done" with a missing or
  unmeasured artifact caught by a negative test) make this CI-checkable, not
  asserted.
- **No empty-work "delivery":** ED-5 + FR-001 fix the proof to ONE
  Founder-scoped, immutable deliverable — no self-scoping, no widening, and
  explicitly no narrowing-to-what-is-easy; an ambiguous boundary halts at the
  Clarify gate (ADR-0014) and escalates, never re-scoped silently. Scope cannot
  be gamed down to nothing.

**Proof scope fixed (FR-001, Q1, immutable):** PROOF project = the **WS-H
control-plane dashboard slice** (e.g. the CP-3b trigger-run). It lives entirely
under `projects/<proof-name>/` (Project Placement Law), its work tickets on its
own board — never `board/tickets/` — and it runs its OWN six AADL gates. Its
skeleton is NOT created here; it is bootstrapped later by DAS-1593. "Shipped" =
merged + green CI + deployed to the tenant VM (Q7): the deploy-to-VM step
(DAS-1595) and the live 0→100 run are genuinely infra-gated (need a provisioned
tenant VM) and, absent it, are carried as `blocked` with a precise reason —
never faked or skipped. The org-engine WS-G machinery this contract governs
(golden-eval/scorecard, evidence/attestation gate, project skeleton) is
buildable now and proceeds.

**SPEC-007 review:** Status `draft` → `reviewed`. FR-001…008 / SC-001…005 are
coherent, testable, and traceable to ADR-0037 ED-1…ED-5; no `[NEEDS
CLARIFICATION]` markers open. No FR-/SC- id tokens added during review.

**Feature flag:** `ws_g_proof` confirmed present in `config/features.yaml` at
`false` (DEFAULT OFF, landed by DAS-1543 — confirmed, not re-added).

**No defect found — not a rubber-stamp:** the contract is evidence-gated and the
proof is scope-locked; no path to a false-green or an empty-work delivery was
left open.

**Verify (LOCAL-ONLY, no PR/CI — doc/governance ticket):**
- `python3 scripts/check_spec_consistency.py` → exit 0 (10 SPECs OK)
- `python3 scripts/check_links.py` → exit 0 (no broken relative links)
- `python3 scripts/board_lint.py` → exit 0 (180 tickets; only the pre-existing
  non-fatal DAS-1507 body-status WARN)

Unblocks **DAS-1590** (WS-G Design). Touched only ADR-0037, `docs/adr/README.md`,
SPEC-007, and this ticket.
</content>
