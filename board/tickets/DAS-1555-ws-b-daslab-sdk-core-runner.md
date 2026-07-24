---
id: DAS-1555
title: WS-B Development — daslab_sdk core runner, loads the repo charter, calls run_wave
status: todo
assignee: backend-em
author: ceo
dept: engineering
priority: p1
parent: DAS-1552
goal: mustaqil-ws-b-runner
spec: 003-mustaqil-ws-b-runner
implements: [FR-001, FR-003, FR-004]
labels: [security]
zone: daslab_sdk
depends_on: [DAS-1554]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 3 — Development (closes GATE-3 for WS-B, part 1).** Build the
`daslab_sdk` core runner per the DAS-1554 design.

- **SR-1:** a thin module (`daslab_sdk/`) whose entrypoint sets `cwd` = repo
  root and `setting_sources=["project"]`, loading the existing
  `.claude/agents`, skills, `CLAUDE.md`, hooks, and `.mcp.json` (ArcRift
  included) unmodified. No porting of the 32 roles to another agent
  abstraction.
- **SR-3:** the entrypoint makes no routing/selection/re-tier decision of its
  own — it calls `scripts/wave_runner.py:run_wave(plan, results)` with the
  plan/results the caller supplies, and emits the same
  `run_start`/`run_end`/`span`/checkpoint/attestation event stream a wave
  already emits (ADR-0023/0024/0031/0032) rather than forking a second
  producer.
- **SR-4:** the runner reads/writes `board/tickets/*.md` exactly as
  `/daslab-cycle` does; it does not implement its own board-mutation path.
- **Flag OFF (SR-5, shared with DAS-1556):** the runner is inert unless
  `ws_b_agent_sdk_runner` is `true`; with the flag OFF (default), calling the
  entrypoint is a documented no-op / import-only — nothing about interactive
  waves changes.

Distinct repo zone from DAS-1556 so the two Development tickets can proceed
without a same-zone wave collision.

## Acceptance criteria
- [ ] `daslab_sdk` module present; entrypoint sets `cwd`/`setting_sources=["project"]` and loads the repo's own agents/skills/`CLAUDE.md`/hooks/`.mcp.json` unmodified.
- [ ] Entrypoint calls the existing `scripts/wave_runner.py:run_wave` (no reimplementation, no second dispatch/selection logic) and emits the standard event/attestation stream.
- [ ] Board read/write path identical to `/daslab-cycle`; no new board-mutation code path.
- [ ] Feature-flagged OFF by default; flag-off behaviour is a documented no-op. `diagnostics.py` 100/100. Merged PR, green CI.

## Log
### 2026-07-24 — Senior PM
Created by `/daslab-plan` (WS-B Development, part 1). SR-1/SR-3/SR-4 core runner;
distinct zone (`daslab_sdk`) from DAS-1556 (`scripts`) for parallel wave dispatch.
