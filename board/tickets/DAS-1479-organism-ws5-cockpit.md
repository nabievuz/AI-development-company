---
id: DAS-1479
title: ORGANISM WS5 — COCKPIT (ops console)
status: done
assignee: cto
author: ceo
dept: engineering
priority: p1
parent: 
goal: organism-ws5-cockpit
created: 2026-07-03
updated: 2026-07-03
---

## Description

**EPIC.** WS5 of Program ORGANISM turns the DasLab engine from *observable* into
*operable*: it kills gap **G7** ("static console — no live ops view, no way to
answer an interrupt in-flow") by shipping a real-time operations console plus an
**Action Console** for answering interrupt-cards. Design pattern **P17**.

**Spec-of-record:** [`docs/research/ORGANISM-PROGRAM-PLAN.md`](../../docs/research/ORGANISM-PROGRAM-PLAN.md)
§4 WS5. This ticket is the epic; the executable work lives in children
**DAS-1480..1482** (per the §4 WS5 table O5-T02/T03/T04, with O5-T01 = the
ADR-0027 form-factor decision).

**EXTEND, do not duplicate.** `scripts/cockpit.py` already exists as
"Operator Cockpit v1" — a PASSIVE, live, six-panel, view-only cockpit. Each of
its 6 panels is bound to a REAL data source via the shared `_render_panel(...)`
renderer and the `NODATA` sentinel (a panel plainly says so when live telemetry
does not yet exist — nothing is mocked, no number is fabricated). WS5 **adds**
panels and an HTML wrapper on top of these existing data-binding functions; it
must NOT stand up a second cockpit. The plan's §3 file-map records
`scripts/cockpit.py → extend` for exactly this reason.

**Data dependency:** the live panels light up only once the WS1↔WS3 dispatch
event-emitter (`board/.events.jsonl`, `run_start`/`run_end`) is emitting real
events. WS5 may run concurrently with WS4, but its "live" acceptance is exercised
against that real event stream; until then panels degrade gracefully to `NODATA`
and a static snapshot.

**Approved form-factor (plan §9 Founder decision #4, default #4 — subject to
ADR-0027):** zero-infra **local auto-refreshing HTML** — stdlib `http.server` or
static regeneration, **no JS build step** — that degrades gracefully to a static
snapshot when nothing is serving. No new service, no framework, no external infra.

**Key files + paths:**
- `scripts/cockpit.py` — EXTEND (6 wired panels + `NODATA` + `_render_panel`; reuse its data-binding funcs).
- `docs/research/ORGANISM-PROGRAM-PLAN.md` — spec-of-record (§4 WS5, §5 ADR-0027).
- `scripts/trends.py` — T1–T7 sparkline source for the new metrics panel.
- `scripts/metrics_lib.py`, `scripts/wave_kpi.py`, `scripts/memory_lib.py` — existing data sources already imported by cockpit.py.
- `board/.events.jsonl` — the live run-feed source (produced by the WS1↔WS3 emitter).
- `docs/adr/` (+ `docs/adr/README.md` index) — ADR-0027 lands here.

**Children (materialized separately):**
- DAS-1480 — Extend `cockpit.render()` panels: live run feed, wave timeline, per-agent success/tokens/tier, per-tool usage, budget burn, T1–T7 sparklines (reuse `NODATA`/`_render_panel`).
- DAS-1481 — **Action Console**: pending interrupt-cards + copy-paste answer stubs.
- DAS-1482 — HTML auto-refresh wrapper over the data-binding funcs; static-snapshot fallback.

## Acceptance criteria

- [ ] ADR-0027 (cockpit form-factor: zero-infra local auto-refreshing HTML, no JS build, static-snapshot degrade) is merged and indexed in `docs/adr/README.md`.
- [ ] All WS5 children DAS-1480, DAS-1481, DAS-1482 are closed green.
- [ ] The console EXTENDS `scripts/cockpit.py` (reuses `_render_panel`/`NODATA` and existing data-binding funcs) — no second/parallel cockpit is introduced.
- [ ] During a **live run**, the cockpit reflects new dispatches **within one refresh cycle**.
- [ ] **Every §5 contract number** (per-agent success/tokens/tier, per-tool usage, budget burn, wave timeline, T1–T7) is visible on the console.
- [ ] The **Action Console** surfaces pending interrupt-cards such that the Founder can answer an interrupt from it in **< 60 seconds**.
- [ ] When nothing is serving live telemetry, the console degrades gracefully to a **static snapshot** (panels show `NODATA`, no fabricated numbers).
- [ ] No new infra/service/JS-build dependency is added (stdlib `http.server` / static regen only).
- [ ] Org-engine ticket: no `project:` field present (board_lint R9 clean).

## Log

### 2026-07-03 — CEO

Created from ORGANISM WS5 COCKPIT decomposition (/daslab-plan). Spec-of-record: docs/research/ORGANISM-PROGRAM-PLAN.md.
READ: docs/research/ORGANISM-PROGRAM-PLAN.md, scripts/cockpit.py.

EPIC — kills gap G7, pattern P17. EXTEND the existing `scripts/cockpit.py`
(6 wired panels + `NODATA` + `_render_panel`); do NOT build a second cockpit.
Children DAS-1480..1482. Approved §9 default #4: zero-infra local
auto-refreshing HTML (stdlib `http.server` / static regen), no JS build step,
degrade gracefully to a static snapshot. Acceptance: during a live run the
cockpit shows dispatches within one refresh; every §5 contract number is
visible; Founder can answer an interrupt-card from the Action Console in < 60s.
Org-engine scope — no `project:` field.

### 2026-07-03 — Orchestrator (/daslab-run)
Done. EPIC CLOSED — WS5 COCKPIT complete. ADR-0028 (static-regen zero-infra HTML); 13 cockpit panels + Action Console; cockpit_html.py. Founder can answer an interrupt-card from the console in <60s; every §5 number visible. Children DAS-1480/1481/1482 done.
