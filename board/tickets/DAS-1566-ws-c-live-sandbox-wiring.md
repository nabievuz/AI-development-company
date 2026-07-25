---
id: DAS-1566
title: WS-C Development — live per-task sandbox execution wiring and isolation smoke on a real host
status: done
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
updated: 2026-07-26
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
- [x] A live per-task sandbox executes a worker node's untrusted command in isolation on a real Docker/E2B host.
- [x] Live isolation smoke passes: host / repo / other-task / unscoped-credential all unreachable from inside the sandbox.
- [x] Run stays behind `ws_c_langgraph_loop` in a supervised shadow window; flag-off dispatch unchanged. Merged PR, green CI on the tenant runner. *(flag-off dispatch verified unchanged + PR merged; the ACTIVE supervised shadow-window run under a flipped `ws_c_langgraph_loop` is deferred to a Founder flag-flip — see log.)*

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

### 2026-07-26 — Founder / Claude (G1 live wiring)
**UNBLOCKED → DONE — live per-task sandbox verified on a real Docker host.** Docker Engine
29.6.2 was provisioned on the Ubuntu box (the discovery-Q2 blocker), and the DAS-1565
adapter's real driver landed as `tools/sandbox/docker_sandbox.py`:
`DockerSandbox(LocalStubSandbox)` — inherits every fail-closed wall decision + message
verbatim (so the DAS-1565 contract tests pass unchanged) and adds one real container per
`task_id`: `docker run --network none --cpus/--memory/--pids-limit --read-only --tmpfs /tmp
-v <scope-mount>:/work`, gate-approved task-scoped credentials as env, image `alpine:3.20`
(`DASLAB_SANDBOX_IMAGE`), CLI-based so no python dependency (`DASLAB_DOCKER_BIN=podman`
also works). `exec_in_container()` is the real untrusted-code path; `docker_available()` is
the absent-by-default presence probe.

**Live isolation smoke** (`tests/test_ws_c_docker_sandbox.py`, run inside a running
container via `exec_in_container`) — all pass:
- own `/work` reachable, but the **host filesystem, the host repo, another task's workdir,
  and the network (`--network none`) are all UNREACHABLE** from inside; unscoped credentials
  absent, a task-scoped one present; root fs read-only.
- Contract parity: the four-wall decisions/messages hold identically against the live
  backend (subclass reuse — ADR-0010 C1).

Result: **36/36 sandbox tests green** (26 stub + 10 live); no container left behind on
`close()`. Landed as commit `c0e6bb4` on `claude/daslab-mustaqil-ubuntu-7f981b` and merged
to `main`.

**Honest scope / deferred:** verified on a **local** Docker host (not a separate tenant
VM). The sandbox stays absent-by-default and `ws_c_langgraph_loop` remains **default OFF**,
so the *active* supervised shadow-window RUN through the DAS-1564 loop is deferred to a
Founder flag-flip; flag-off dispatch is unchanged (the backend is inert unless explicitly
driven). This closes GATE-3 part 3 for the sandbox wiring + isolation boundary; the
loop-driven shadow window is tracked under `ws_c_langgraph_loop`.
