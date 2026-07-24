---
id: DAS-1592
title: WS-G Development — the 0 to 100 evidence and attestation gate, no false-green
status: todo
assignee: backend-eng-1
author: ceo
dept: engineering
priority: p1
parent: DAS-1588
goal: mustaqil-ws-g-proof
spec: 007-mustaqil-ws-g-proof
implements: [FR-002, FR-004]
labels: [governance]
zone: scripts
depends_on: [DAS-1590]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 3 — Development (closes GATE-3 for WS-G, part 2).** Build the 0→100
evidence + attestation gate per the DAS-1590 design.

- **FR-002/ED-1:** enforce that "finished" is evidenced ONLY — the gate reads the
  run-scorecard (DAS-1591) and fails unless every completion-contract dimension is
  actually met (gates closed, merged PR + green CI, committed attestation,
  `diagnostics.py` 100/100, golden eval + anti-gaming probe).
- **FR-004/ADR-0031/0032:** commit + hash-chain the 0→100 evidence trail onto the
  existing wave attestation (run-start / run-end / span / checkpoint / attestation), so
  a lapse breaks a committed chain and fails CI rather than passing silently.
- **No false-green (ADR-0020):** a "done" with a missing or unmeasured artifact is
  rejected; unmeasured is SKIPPED, never green. Reuse the existing attestation
  primitives (ADR-0031/0032) — do not fork a second attestation producer.
- **FR-007:** behind `ws_g_proof` OFF; flag-off = byte-identical to pre-merge.

## Acceptance criteria
- [ ] The evidence gate reads the run-scorecard and fails on any unmet/unmeasured completion-contract dimension (FR-002).
- [ ] The 0→100 evidence trail is committed + hash-chained onto ADR-0031/0032 attestation; no second/divergent attestation producer (FR-004).
- [ ] A false-green (missing/unmeasured artifact) is rejected — the hand-off case for DAS-1594's SC-004 test.
- [ ] Behind `ws_g_proof` OFF; `diagnostics.py` 100/100. Merged PR, green CI.

## Log
### 2026-07-24 — Senior Product Manager
Created by /daslab-plan (WS-G Development, part 2). FR-002/FR-004 evidence + attestation
gate; reuses ADR-0031/0032; no false-green (ADR-0020); behind `ws_g_proof` OFF.
</content>
