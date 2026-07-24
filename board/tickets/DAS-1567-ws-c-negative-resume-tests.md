---
id: DAS-1567
title: WS-C Testing — resume idempotency, gate-interrupt block, routing rejection, divergence and flag-off
status: todo
assignee: qa-eng
author: ceo
dept: engineering
priority: p1
parent: DAS-1561
goal: mustaqil-ws-c-loop
spec: 004-mustaqil-ws-c-loop
implements: [SC-001, SC-002, SC-003, SC-004, SC-005]
labels: [security]
zone: tests
depends_on: [DAS-1564, DAS-1565]
created: 2026-07-24
updated: 2026-07-24
---


## Description

**AADL Stage 4 — Testing (closes GATE-4 for WS-C).** Prove the loop governance holds with
adversarial + resume tests against the DAS-1564 substrate and the DAS-1565 sandbox adapter
(stub backend — live-host smoke is DAS-1566). Security Engineer (red team) consulted.

Cover:
- **SC-001:** an idempotent checkpoint/resume test — the loop resumes after a mid-run
  interruption without losing progress and without double-applying a committed side effect
  (DAS-1447 guard-before-act).
- **SC-002:** a ticket behind an open gate is NOT routed to a worker node (gate =
  `interrupt()`/conditional edge, LG-2/C4); and an injected `graph_state` divergence
  resolves back to the board (board wins, LG-1/C2).
- **SC-003:** a worker node's attempt to write a routing field (assignee/reviewer/
  routing_reason/confidence) is rejected / structurally impossible (LG-3/C3).
- **SC-004:** with `ws_c_langgraph_loop` OFF, a wave's dispatch is byte-identical to
  pre-merge; flipping it ON runs the loop only in shadow.
- Sandbox isolation asserted at the adapter/stub layer (host/repo/other-task/credential
  unreachable by default); live-host smoke is DAS-1566.

## Acceptance criteria
- [ ] Negative/resume tests exist and PASS in CI for SC-001 (idempotent resume), SC-002 (gate-block + divergence-resolves-to-board), and SC-003 (routing-field rejection).
- [ ] Flag-off no-op behaviour asserted (SC-004); flag-on runs shadow-only.
- [ ] Sandbox isolation policy asserted against the stub backend; overall pytest green in CI.
- [ ] Security Engineer red-team review recorded. Merged PR, green CI.

## Log
### 2026-07-24 — CEO
Created by /daslab-plan (WS-C Testing). SC-001 resume idempotency, SC-002 gate-block +
divergence, SC-003 routing rejection, SC-004 flag-off; red-team consulted. Live-host
isolation smoke is DAS-1566 (blocked, external dependency).

### 2026-07-24 — CTO
Bound **SC-005** into `implements:` at DAS-1563 GATE-2 closure. The WS-C design
(`docs/design/ws-c-langgraph-loop.md` §7 SC-005a–d) routes the FR-006 sandbox-escape
negative test (host/repo escape, cross-task isolation, unscoped-credential + egress,
resource-limit) to this ticket, run against the `LocalStubSandbox` (host-free); the same
refusal decisions re-run unchanged against DAS-1566's live `DockerSandbox`. SC-005 is a
valid SPEC-004 token, so the ref resolves and `check_spec_consistency` stays green. Note:
SPEC-004's SC-005 is literally worded as the CI-hygiene criterion (diagnostics/validators/
green CI/committed attestation); the design overloads the same id as the sandbox-escape
umbrella — both readings land on this ticket. No other field changed.
</content>
