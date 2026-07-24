---
id: DAS-1562
title: WS-C Planning — author and ratify ADR-0035, review SPEC-004, confirm the WS-C key OFF
status: todo
assignee: cto
author: ceo
dept: engineering
priority: p1
parent: DAS-1561
goal: mustaqil-ws-c-loop
spec: 004-mustaqil-ws-c-loop
implements: [FR-001, FR-007]
labels: [governance]
zone: docs/adr
depends_on: [DAS-1543]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 1 — Planning (closes GATE-1 for WS-C).**

- Finalize + ratify **ADR-0035** (currently `Proposed`, Backend EM authors) → `Accepted`
  after **CTO** sign-off (RACI 3.1/3.6). **Security Lead consulted** on the sandboxed
  worker runner + secrets. Verify LG-1…LG-5 hold against DGO-X C1–C6 (ADR-0010), the
  ADR-0034 runner as node-execution admission, ADR-0023 checkpoints, ADR-0025
  flag-on==flag-off, and ADR-0031/0032 attestation.
- Review `docs/specs/004-mustaqil-ws-c-loop/SPEC.md` (FR-001…FR-007, SC-001…SC-005);
  resolve any `[NEEDS CLARIFICATION]`; mark SPEC Status `reviewed`.
- Confirm the WS-C feature key `ws_c_langgraph_loop` is present in `config/features.yaml`
  DEFAULT **OFF** (landed by the DAS-1543 scaffold) — confirm only, do not re-add.
- Record the **WS-B sequence constraint**: WS-C may not drive ahead of WS-B's AADL gate
  (ADR-0035 `depends_on 0034`); WS-B is not yet on the board.

No substrate or sandbox is built in this stage — this fixes the contract the WS-C code
builds against.

## Acceptance criteria
- [ ] ADR-0035 Status flipped to `Accepted` with the CTO sign-off recorded; Security Lead consult on the sandboxed runner captured; `docs/adr/README.md` consistent.
- [ ] SPEC-004 reviewed (Status `reviewed`), no unresolved clarification markers.
- [ ] `ws_c_langgraph_loop` confirmed present in `config/features.yaml`, value `false` (from DAS-1543 — not re-added).
- [ ] WS-B sequence constraint recorded in the log so `/daslab-run` does not drive WS-C early.
- [ ] `check_spec_consistency`/`check_links`/`board_lint` green. (Doc/governance ticket, LOCAL-ONLY — no PR/CI exists; exempt from the merged-PR done-gate, accepted on local green.)

## Log
### 2026-07-24 — CEO
Created by /daslab-plan (WS-C Planning). Ratifies ADR-0035 (under DGO-X C1-C6); reviews
SPEC-004; confirms the loop flag OFF. Security Lead consulted on the sandboxed worker
runner per ADR-0035.
</content>
