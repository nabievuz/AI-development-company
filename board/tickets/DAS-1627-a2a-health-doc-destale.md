---
id: DAS-1627
title: De-stale the A2A health doc now that its runner and schedule entry exist
status: done
assignee: tech-writer
author: backend-em
dept: product
priority: p2
parent: DAS-1606
goal: mustaqil-a2a-outbound
spec: 009-mustaqil-a2a-outbound
implements: [SC-003]
labels: [security]
zone: docs/06-maintenance
depends_on: [DAS-1624]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**Raised by Backend EM during the DAS-1624 review.** `docs/06-maintenance/ws-a2a-outbound-health.md`
was written by DAS-1614 under a `docs/06-maintenance/` zone lock, at a moment when
the `scripts/`-zone wiring genuinely did not exist. DAS-1624 then landed that
wiring — so the doc went stale the moment that ticket closed.

Three specific staleness points the reviewer identified:
1. It declares the `feature_flags.DEFAULTS` gap as "not fixed here". It **is**
   fixed — `a2a_outbound: False` is in `DEFAULTS` as of DAS-1624.
2. It describes the `scripts/` wiring as un-done follow-up. It **is** done —
   `scripts/ws_a2a_health_check.py` exists and `ws-a2a-outbound-health` is
   registered in `stage_gate.maintenance_schedule()`.
3. It never names `scripts/ws_a2a_health_check.py` as its runner, so a reader
   cannot get from the doc to the thing that executes it. Every sibling health
   doc names its runner.

**Prose-only. The behavior is correct** — this is documentation catching up to
shipped code, not a defect. Do not change any check's semantics, do not touch the
runner, and do not re-litigate DAS-1614's or DAS-1624's decisions.

Keep the doc honest about what it currently is: the A2A surface is
**merged-but-dark** — `a2a_outbound` is `false`, the endpoint has never been
published, and `board/.events.jsonl` holds zero `a2a_publish` events. The checks
are armed and run against the dark surface today; the live-surface legs activate
on the Founder flip. Do not let the de-staling drift into implying anything is
being monitored in production.

⛔ Do NOT flip `a2a_outbound`. Publishing the endpoint is a Founder-only act
(QONUN-5, FR-003).

## Acceptance criteria
- [x] The three staleness points above corrected against the actual current state of `scripts/ws_a2a_health_check.py`, `scripts/stage_gate.py`, and `scripts/feature_flags.py` — verified by reading them, not assumed.
- [x] The doc names its runner and the exact command the scheduler invokes, matching the registered `ws-a2a-outbound-health` entry verbatim.
- [x] The merged-but-dark framing preserved — no implication of production monitoring.
- [x] `check_links.py` green; `diagnostics.py` 100/100; `board_lint`/validators green; no `project:` field (R9).

## Log
### 2026-07-24 — Backend EM
Raised as R2 in the DAS-1624 review report; recorded by the orchestrator in the
same run. Outside that review's zone lock (`scripts`/`tests`/`tools/a2a`), so left
untouched there. Does not reopen any closed A2A gate — DAS-1607..DAS-1614 all stay
`done`.

### 2026-07-24 — Technical Writer
De-staled all three staleness points by reading the real implementation files:

1. **DEFAULTS gap fixed** — Verified line 42 of `scripts/feature_flags.py`:
   `"a2a_outbound": False` is now in DEFAULTS. Updated the doc (lines 93–97)
   to reflect that the gap IS fixed and `feature_flags.enabled("a2a_outbound")`
   now resolves correctly. Confirmed the runner uses it at line 133 of
   `scripts/ws_a2a_health_check.py`.

2. **Scheduler entry exists** — Verified lines 529–543 of `scripts/stage_gate.py`:
   the `ws-a2a-outbound-health` entry is registered in
   `maintenance_schedule()["recurring_runs"]` with command
   `["python3", "scripts/ws_a2a_health_check.py", "--json"]` and cadence "daily".
   Updated the "Cadence and registration" section (lines 125–127) to state the
   wiring IS done (removed "follow-up work" language) and added the verbatim
   command.

3. **Runner script named** — Added "Check script" section (lines 30–39) mirroring
   the style of sibling health docs (`ws-e-tenant-health.md`), naming the runner
   and its registration point. The doc now shows a reader exactly where the
   executor lives and how it's scheduled.

Preserved the merged-but-dark framing throughout — no implication of production
monitoring, all checks armed and running against dark surface, publish stays
Founder-only (QONUN-5/FR-003).

Verified: check_links.py ✓, board_lint ✓, git diff config/features.yaml empty,
git status shows only zone-lock files changed.
