---
id: DAS-1594
title: WS-G Testing — negative tests for false-green rejection and scorecard skip
status: todo
assignee: qa-eng
author: ceo
dept: engineering
priority: p1
parent: DAS-1588
goal: mustaqil-ws-g-proof
spec: 007-mustaqil-ws-g-proof
implements: [SC-001, SC-004]
labels: [governance]
zone: tests
depends_on: [DAS-1591, DAS-1592]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 4 — Testing (closes GATE-4 for WS-G).** Prove the evidence machinery holds
with adversarial negative tests. Security Engineer (red team) consulted.

Cover:
- **SC-001:** the run-scorecard scores each completion-contract dimension (gates closed,
  merged PR + green CI, committed attestation, `diagnostics.py` 100/100, golden eval +
  anti-gaming probe); a dimension that cannot be measured is reported SKIPPED, never
  counted green.
- **SC-004:** a false-green attempt — a unit claimed "done" with a missing or unmeasured
  artifact — is caught by the evidence gate / anti-gaming probe and fails.
- **SC-003 guard:** with `ws_g_proof` OFF, dispatch is byte-identical to pre-merge and
  the harness/scorecard is inert.

## Acceptance criteria
- [ ] Negative tests exist and PASS in CI for SC-001 (per-dimension scoring + SKIPPED-not-green) and SC-004 (false-green rejected).
- [ ] Flag-off no-op behaviour asserted (SC-003).
- [ ] Anti-gaming probe proven — a fabricated "done" without a real artifact does not score green.
- [ ] Security Engineer red-team review recorded. Merged PR, green CI.

## Log
### 2026-07-24 — Senior Product Manager
Created by /daslab-plan (WS-G Testing). SC-001/SC-004 negative tests; anti-gaming +
false-green rejection; flag-OFF no-op guard; red-team consulted.
</content>
