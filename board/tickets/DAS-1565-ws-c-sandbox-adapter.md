---
id: DAS-1565
title: WS-C Development — E2B and OpenHands per-task sandbox adapter, isolation boundary, stub backend
status: todo
assignee: backend-eng-1
author: ceo
dept: engineering
priority: p1
parent: DAS-1561
goal: mustaqil-ws-c-loop
spec: 004-mustaqil-ws-c-loop
implements: [FR-006]
labels: [security]
zone: tools/sandbox
depends_on: [DAS-1563]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 3 — Development (closes GATE-3 for WS-C, part 2).** Build the per-task
**sandbox adapter** a worker node uses to run untrusted code/commands in isolation, per the
DAS-1563 isolation contract. Security Lead consulted.

- **FR-006:** an isolation boundary (E2B / OpenHands, Docker-based per Q2) — untrusted
  execution cannot reach the host, the repo, another task, or a credential it was not
  explicitly scoped (fail-closed default: no host mounts, no network, no creds).
- **Stub/reference backend (buildable without a live host):** follow the WS-A pattern —
  the real Docker/E2B driver is an **optional, absent-by-default** dependency
  (`tools/sandbox/requirements-sandbox.txt`, kept out of core `requirements.txt`); the
  adapter is importable/testable with zero optional deps installed against a stub backend.
  The sandbox therefore *does not exist* until the optional backend is installed.
- Feature-flagged OFF (the shared `ws_c_langgraph_loop` key) — with the flag OFF the
  adapter is inert and dispatch is unchanged.
- **Actually running a live sandbox/VM is OUT of scope here** — that is DAS-1566 (blocked
  on a live host). This ticket delivers the adapter + isolation policy + tests against the
  stub, which are fully buildable in-repo.

Distinct repo zone (`tools/sandbox/`) from the LangGraph substrate (DAS-1564) so the two
Development tickets don't collide in one wave.

## Acceptance criteria
- [ ] Per-task sandbox adapter under `tools/sandbox/` with a fail-closed isolation policy (no host mount / no network / no creds by default); real driver is an optional absent-by-default dep.
- [ ] Adapter importable + unit-testable against the stub backend with zero optional deps installed; the sandbox does not exist unless the optional backend is installed.
- [ ] Isolation-policy tests pass against the stub (host/repo/other-task/credential unreachable by default); live-host isolation smoke deferred to DAS-1566.
- [ ] Feature flag OFF by default; flag-off dispatch unchanged; `diagnostics.py` 100/100. Merged PR, green CI.

## Log
### 2026-07-24 — CEO
Created by /daslab-plan (WS-C Development, part 2). FR-006 per-task sandbox adapter
(E2B/OpenHands), stub-backend buildable like the WS-A tool bridge; behind
`ws_c_langgraph_loop` OFF. Live-host execution split out to DAS-1566 (external dependency).
Security Lead consulted on the isolation boundary.
</content>
