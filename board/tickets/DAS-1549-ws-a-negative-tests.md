---
id: DAS-1549
title: WS-A Testing — negative tests for grant refusal, audit-skip denial, egress block, redaction
status: todo
assignee: qa-eng
author: ceo
dept: engineering
priority: p1
parent: DAS-1544
goal: mustaqil-ws-a-reach
spec: 002-mustaqil-ws-a-reach
implements: [SC-001, SC-002]
labels: [security]
zone: tests
depends_on: [DAS-1547, DAS-1548]
created: 2026-07-23
updated: 2026-07-23
---

## Description

**AADL Stage 4 — Testing (closes GATE-4 for WS-A).** Prove the governance holds with
adversarial negative tests. Security Engineer (red team) consulted.

Cover:
- **SC-001:** a globally-granted tool (no overlay allow-list) is refused (TB-2); a call
  that skips the `PreToolUse` audit is denied (TB-3).
- **SC-002:** browser egress to a non-allow-listed domain is blocked (TB-4/Q5); a
  tool-event redaction probe passes (ADR-0012).
- **SC-003 guard:** with the flag OFF, dispatch is byte-identical to pre-merge.
- Fold in and extend `tests/test_ws_a_tool_bridge.py`.

## Acceptance criteria
- [ ] Negative tests exist and PASS in CI for SC-001 (grant refusal + audit-skip denial) and SC-002 (egress block + redaction probe).
- [ ] Flag-off no-op behaviour asserted (SC-003).
- [ ] `tests/test_ws_a_tool_bridge.py` folded in and green; overall pytest green in CI.
- [ ] Security Engineer red-team review recorded. Merged PR, green CI.

## Log
### 2026-07-23 — CEO
Created by /daslab-plan (WS-A Testing). SC-001/SC-002 negative tests; red-team consulted.
