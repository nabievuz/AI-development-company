---
id: DAS-1612
title: A2A Testing — negative tests for gate-bypass, self-approval, admission-skip, redaction
status: backlog
assignee: qa-eng
author: ceo
dept: engineering
priority: p1
parent: DAS-1606
goal: mustaqil-a2a-outbound
spec: 009-mustaqil-a2a-outbound
implements: [SC-001, SC-002, SC-004]
labels: [security]
zone: tests
depends_on: [DAS-1610, DAS-1611]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 4 — Testing (closes GATE-4 for A2A OUTBOUND).**

Write and run the negative-test suite proving the A2A surface cannot be used to
weaken governance:

- **Gate-bypass test (SC-001):** an external A2A call cannot advance a ticket
  past an open AADL gate, and cannot cause self-approval.
- **Goal-proposal-not-approval test (SC-002):** a goal proposal submitted via
  A2A lands only as a board-intake artifact; assert it never flips an
  `approval`/gate-status field, however it is shaped or repeated.
- **Admission-skip test (SC-004):** a call that attempts to skip the ADR-0009
  admission layer is denied.
- **Redaction probe (SC-004):** any transcript/payload crossing the A2A boundary
  is ADR-0012 classified and redacted before it leaves the process — no secret
  or unredacted content survives.
- **Flag-OFF regression:** with `a2a_outbound` OFF, prove dispatch/board behavior
  is byte-identical to a pre-merge baseline (feeds SC-005, confirmed again at
  Deployment).

## Acceptance criteria
- [ ] Negative test proves an A2A call cannot advance a ticket past an open gate or self-approve (SC-001).
- [ ] Negative test proves a goal proposal cannot become an approval, under any input shape (SC-002).
- [ ] Negative test proves an admission-skip attempt is denied (SC-004).
- [ ] Redaction probe passes on A2A boundary transcripts (SC-004).
- [ ] Flag-OFF regression test passes (byte-identical dispatch/board behavior).
- [ ] Merged PR, green CI; `diagnostics.py` 100/100; no `project:` field (R9).

## Log
### 2026-07-24 — Senior Product Manager
Created by `/daslab-plan` (A2A Testing). Depends on both Development children
(DAS-1610, DAS-1611). Gated behind DAS-1606's binding sequencing note (after
WS-B, deferred until after WS-G's proof per Q12) — left in `status: backlog`
until that gate opens.
