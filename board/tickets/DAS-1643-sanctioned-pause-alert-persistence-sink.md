---
id: DAS-1643
title: Route the sanctioned-pause SI-5 alert to a monitored sink outside the tick
status: backlog
assignee: sre-eng
author: sre-lead
dept: engineering
priority: p2
parent: DAS-1615
goal: mustaqil-ws-f-tempo
spec: 010-mustaqil-ws-f-tempo
implements: [FR-004]
labels: [governance]
zone: scripts
depends_on: [DAS-1634]
created: 2026-07-25
updated: 2026-07-25
---

## Description

**Deferred residual routed from the DAS-1634 review. Backlog, not this run's work —
it is at parity with the rest of the alerting surface, which is trigger-gated with no
live sink today.**

DAS-1634 wired the SI-5 alert limb: `alerting.sanctioned_pause_alert` is emitted from
`loop_controller.tick()` and printed on the `--tick` surface. That satisfies FR-004's
"idle + alert" on the surface an operator watching a tick sees. What it does NOT do is
**persist** the alert to a channel an operator monitors when they are *not* staring at
tick stdout — nothing appends it to `board/.events.jsonl` or routes it onward.

**Why this is deferred, not open-and-urgent:** the entire `scripts/alerting.py` surface
is by design trigger-gated with no live sink yet (P5 alerting, DAS-1461). The
sanctioned-pause alert is at exact parity with every other alert this repo emits — none
of them persist yet. Building a sink for this one alert alone would be premature and
would fragment the eventual consolidated alerting consumer. So this waits until there is
a real alerting sink to attach to, or until go-live makes persistence load-bearing.

**The one hard constraint when it IS built:** the sink must live OUTSIDE `tick()`.
`tick()` is a pure, non-mutating evaluator — writing to `board/.events.jsonl` from
inside it breaches SI-2 (the tick performs no state mutation), which is one of the
invariants WS-F exists to protect. A separate consumer reads the tick's returned
`alert` (or re-derives it) and persists it; the tick itself stays pure.

**Reassess trigger:** promote this out of `backlog` when either (a) a live alerting sink
lands for the broader `alerting.py` surface, or (b) HEARTBEAT go-live is imminent and a
silent-in-the-log sanctioned pause becomes an operational risk rather than a
theoretical one.

⛔ Do NOT flip `heartbeat_enabled`. Do NOT make `tick()` mutate state (SI-2). Do NOT
build a bespoke second alerting notifier — attach to the consolidated path when it exists.

## Acceptance criteria
- [ ] A consumer OUTSIDE `tick()` persists / routes the sanctioned-pause SI-5 alert to a monitored channel; `tick()` remains pure (SI-2 intact).
- [ ] It reuses the consolidated alerting sink rather than a bespoke second notifier.
- [ ] A sanctioned pause is discoverable after the fact from the persisted record, not only from live tick stdout.
- [ ] `diagnostics.py` 100/100; full suite green; `board_lint`/validators green; no `project:` field (R9).

## Log
### 2026-07-25 — SRE / DevOps Lead
Routed from the DAS-1634 review as the genuine residual behind the accepted close.
Filed `status: backlog` / `p2`/`backlog` deliberately: it is at parity with the whole
trigger-gated alerting surface (no alert persists today), so building a sink for this
one alert now would be premature and fragmenting. Recorded by the orchestrator in the
same run so the residual is tracked rather than lost, with an explicit reassess trigger.
