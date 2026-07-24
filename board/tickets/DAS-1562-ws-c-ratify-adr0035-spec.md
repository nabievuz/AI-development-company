---
id: DAS-1562
title: WS-C Planning — author and ratify ADR-0035, review SPEC-004, confirm the WS-C key OFF
status: done
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
- [x] ADR-0035 Status flipped to `Accepted` with the CTO sign-off recorded; Security Lead consult on the sandboxed runner captured; `docs/adr/README.md` consistent.
- [x] SPEC-004 reviewed (Status `reviewed`), no unresolved clarification markers.
- [x] `ws_c_langgraph_loop` confirmed present in `config/features.yaml`, value `false` (from DAS-1543 — not re-added).
- [x] WS-B sequence constraint recorded in the log so `/daslab-run` does not drive WS-C early.
- [x] `check_spec_consistency`/`check_links`/`board_lint` green. (Doc/governance ticket, LOCAL-ONLY — no PR/CI exists; exempt from the merged-PR done-gate, accepted on local green.)

## Log
### 2026-07-24 — CEO
Created by /daslab-plan (WS-C Planning). Ratifies ADR-0035 (under DGO-X C1-C6); reviews
SPEC-004; confirms the loop flag OFF. Security Lead consulted on the sandboxed worker
runner per ADR-0035.

### 2026-07-24 — CTO — GATE-1 (WS-C Planning) CLOSED
AADL Stage-1 Planning gate for WS-C LOOP closed. A→B→C sequence satisfied (WS-B complete);
WS-B sequence constraint stands: WS-C code may not drive ahead of WS-B's gate (ADR-0035
`depends_on 0034`), and the flip stays OFF until a supervised 0→100 slice lands (Q4).

**1. ADR-0035 ratified — VERDICT: sound, `Proposed` → `Accepted`.** Judged LG-1…LG-5
verbatim against ADR-0010 C1–C6, plus ADR-0023/0025/0031/0032/0034. The load-bearing
C1/C2 "is LangGraph the org brain?" check answers **NO**: LG-1 binds LangGraph as an
execution *projection* of `graph_state`, which is itself a mirror of the canonical
`board/tickets/*.md`; LangGraph is explicitly never the top-level source of truth, no
DasLab law moves into it, and any divergence resolves to the board (C2). No LangGraph
state can become the top-level dispatcher — DGO-X wins any model conflict, the mapping
absorbs it. Gates are conditional edges/`interrupt()` that halt for the Founder (LG-2/C4,
GATE-5-open stays machine-blocked); workers never write routing fields (LG-3/C3);
checkpoint/resume reconciles with the ADR-0023 run-model and the ADR-0031/0032 attestation
ledger, never forks a second truth, and runs post-decision mechanics through `run_wave` so
ADR-0025 flag-on==flag-off holds and the event store stays audit system-of-record (LG-4);
lands behind `dgox_emit` OFF, shadow-before-drive, ADR-0034 SDK runner as the sole
node-execution admission layer, ADR-0009 ceiling not re-opened (LG-5/C5). E2B/OpenHands
per-task sandbox = optional in-tenant admission infra, not truth. Dated CTO sign-off
recorded in the ADR (Status line + Enforcement/acceptance); Security Lead consult on the
sandboxed runner + secrets captured. `docs/adr/README.md` row 0035 → Accepted (2026-07-24).
No defect found; no C1/C2 violation — not a rubber-stamp.

**2. SPEC-004 reviewed → `reviewed`.** FR-001…FR-007 / SC-001…SC-005 are coherent, each
FR carries one testable MUST and traces to ADR-0035 LG-1…LG-5 (+ C1–C6, ADR-0023/0025);
SC-001…SC-005 are measurable and bind back (checkpoint/resume idempotency DAS-1447,
gate-not-routed + divergence-to-board negative tests, routing-field rejection, flag-OFF
byte-identity, diagnostics/validators + attestation). No `[NEEDS CLARIFICATION]` markers.
Reviewer observation (NON-blocking, no SPEC edit made — per the no-duplicate-id rule): the
per-task sandbox isolation requirement (FR-006) has no dedicated SC token; it is coherent
here because the live sandbox is Q2-deferred/blocked (DAS-1566) and its escape-negative
test is owned by the Stage-2 design ticket under SC-005's validator/attestation umbrella.
Carry to WS-C Design (DAS-1563) — do not treat FR-006 as untested at build time.

**3. Feature flag confirmed (not re-added).** `ws_c_langgraph_loop: false` present in
`config/features.yaml` (line 22, landed by DAS-1543) — DEFAULT OFF, consumer = the finisher
loop, flip is a Founder-only act after a supervised 0→100 slice (Q4). Confirm only.

**VERIFY (exact):** `python3 scripts/check_spec_consistency.py` → exit 0 (10 SPECs OK);
`python3 scripts/check_links.py` → exit 0 (no broken links); `python3 scripts/board_lint.py`
→ exit 0 (180 tickets, 0 violations; the single WARN is on unrelated DAS-1507, non-fatal).
GATE-1 closed on local green. LOCAL-ONLY: no commit/push/PR. Unblocks DAS-1563 (WS-C Design).
</content>
