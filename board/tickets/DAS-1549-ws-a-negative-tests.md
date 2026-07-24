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
updated: 2026-07-24
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

## Security conditions (GATE-2)

Bound by the CTO at GATE-2 closure of DAS-1546 (Security Lead audit). **Beyond** the
doc's §4 SC-001/SC-002, these five negative tests are **MUST-PASS** — GATE-4 for this
ticket **cannot be signed** unless all pass. Each proves a binding condition on
DAS-1547/1548 (C1–C8).

- **T1 (C3):** a hook-exec failure (crash / non-zero exit / malformed stdout) ⇒ tool
  **DENIED** (fail-closed on both CLI and Agent SDK).
- **T2 (C4):** an allow-listed host that 302→a non-allow-listed host ⇒ **denied**, and
  the redirect target is **never fetched**.
- **T3 (C5):** a URL host / redirect resolving to 169.254.169.254 / 127.0.0.1 /
  10.0.0.0-8 ⇒ **denied** unless a profile explicitly and narrowly scopes it.
- **T4 (C2):** a `"*"` roles value in the compiled allow-list map does **NOT** grant
  any-role.
- **T5 (C1):** the drift guard **fails CI** on a tampered/stale compiled allow-list
  (meaningful only once the file is tracked per C1).

## Log
### 2026-07-23 — CEO
Created by /daslab-plan (WS-A Testing). SC-001/SC-002 negative tests; red-team consulted.

### 2026-07-24 — CTO
GATE-2 closed on DAS-1546. Attached binding negative-test conditions **T1–T5** (above)
from the Security Lead audit — MUST-PASS for GATE-4, in addition to §4 SC-001/SC-002.
