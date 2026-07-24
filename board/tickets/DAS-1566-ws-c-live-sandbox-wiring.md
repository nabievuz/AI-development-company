---
id: DAS-1566
title: WS-C Development — live per-task sandbox execution wiring and isolation smoke on a real host
status: blocked
assignee: sre-eng
author: ceo
dept: engineering
priority: p1
parent: DAS-1561
goal: mustaqil-ws-c-loop
spec: 004-mustaqil-ws-c-loop
implements: [FR-006]
labels: [security]
zone: tools/sandbox
depends_on: [DAS-1564, DAS-1565]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 3 — Development (closes GATE-3 for WS-C, part 3).** Wire the DAS-1565 sandbox
adapter to a **real Docker/E2B host** and run a live isolation smoke — a worker node
executes untrusted code inside an actual per-task sandbox and the isolation boundary
(no host reach, no repo reach, no cross-task reach, no unscoped creds) is verified against
a running container/VM, not a stub. Security Lead consulted; SRE Lead accountable for the
tenant host.

- Provision the in-tenant Docker/E2B sandbox host (one Linux VM per discovery Q2).
- Swap the DAS-1565 stub backend for the real driver via
  `tools/sandbox/requirements-sandbox.txt` (optional, absent-by-default) on that host.
- Run the live isolation smoke + a real worker-node round-trip through the DAS-1564
  substrate, behind `ws_c_langgraph_loop` in a shadow window (Q4 supervised).

## Acceptance criteria
- [ ] A live per-task sandbox executes a worker node's untrusted command in isolation on a real Docker/E2B host.
- [ ] Live isolation smoke passes: host / repo / other-task / unscoped-credential all unreachable from inside the sandbox.
- [ ] Run stays behind `ws_c_langgraph_loop` in a supervised shadow window; flag-off dispatch unchanged. Merged PR, green CI on the tenant runner.

## Log
### 2026-07-24 — CEO
Created by /daslab-plan (WS-C Development, part 3).

**BLOCKED — external dependency (no live sandbox host).** This ticket requires *actually
running* a live Docker/E2B sandbox or VM to verify isolation on real infrastructure. A
planning/authoring agent has **no live sandbox host** and cannot provision the tenant Linux
VM (discovery Q2) or install the real E2B/OpenHands driver. Per the MUSTAQIL WS-C dispatch
rule, any ticket that needs a live sandbox/VM is parked `blocked` while the buildable
adapter/substrate work (DAS-1564 substrate, DAS-1565 sandbox adapter + stub tests) proceeds
`todo`. **Unblocks when:** the in-tenant Docker/E2B host is provisioned and DAS-1564 +
DAS-1565 are `done`. Routed to the orchestrator/Founder for host provisioning — not
auto-dispatched.
</content>
