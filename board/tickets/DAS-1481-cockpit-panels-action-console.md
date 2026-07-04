---
id: DAS-1481
title: Extend cockpit panels and add Action Console
status: done
assignee: cto
author: ceo
dept: engineering
priority: p1
parent: DAS-1479
goal: organism-ws5-cockpit
depends_on: [DAS-1480]
zone: cockpit
created: 2026-07-03
updated: 2026-07-03
---

## Description

GATE-3 (P17) work for ORGANISM WS5 COCKPIT. The cockpit is the Founder's
single-glance operating surface: it must render every §5 contract number
(T1–T7, spans, cost) and let the Founder answer pending decisions in under
60 seconds.

**What/why.** `scripts/cockpit.py` already renders a cockpit from the event
store using a `NODATA` sentinel and a shared `_render_panel` helper. This
ticket EXTENDS that renderer IN PLACE (no second cockpit) so the Founder sees
the live run feed, wave timeline, per-agent and per-tool usage, budget burn,
and the T1–T7 sparklines — plus a new **Action Console** that surfaces pending
interrupt-cards with copy-paste answer stubs.

**Extend-vs-new.** Reuse the existing `render()`/panel machinery, the `NODATA`
sentinel, and `_render_panel` from `scripts/cockpit.py`. Do NOT create a second
cockpit script or a parallel renderer. New panels are added to the existing
render path; the Action Console is a new panel within the same cockpit.

**Data sources.** Panel data comes from the event store (already read by
`cockpit.py`) plus the cost-ledger (`scripts/cost/cost_ledger.py`) for budget
burn, `scripts/trends.py` for the T1–T7 sparklines, and `scripts/metrics_lib.py`
/ `scripts/wave_kpi.py` for per-agent and per-wave aggregates. The Action
Console reads pending cards from `board/interrupts/` (see
`board/interrupts/README.md` for the card schema). Any panel with no data
renders the existing `NODATA` sentinel — never a crash, never a blank.

**Key files + paths (READ these first):**
- `scripts/cockpit.py` — extend `render()` / panels in place; reuse `NODATA`, `_render_panel`
- `scripts/trends.py` — T1–T7 sparkline source
- `scripts/wave_kpi.py` — wave timeline + per-wave KPI aggregates
- `scripts/cost/cost_ledger.py` — budget burn source
- `scripts/metrics_lib.py` — per-agent success/tokens/tier aggregates
- `board/interrupts/README.md` — interrupt-card schema for the Action Console
- `board/interrupts/` — pending interrupt-cards to list

Spec-of-record: `docs/research/ORGANISM-PROGRAM-PLAN.md`.

## Acceptance criteria

- [ ] New panels added: run-feed (live), wave-timeline, per-agent
      (success/tokens/tier), per-tool usage, budget burn (from cost-ledger),
      and T1–T7 sparklines (from `trends.py`)
- [ ] Action Console panel lists pending interrupt-cards from `board/interrupts/`
      with copy-paste answer stubs so the Founder can answer in <60s
- [ ] Renderer reuses existing `NODATA` sentinel and `_render_panel` — extended
      IN PLACE, no second cockpit / no parallel renderer
- [ ] Every §5 contract number visible (T1–T7, spans, cost)
- [ ] Panels source data from the event store + cost-ledger; NODATA when empty
- [ ] Tests cover the new panels and the Action Console (populated + empty/NODATA)
- [ ] Full suite: 0 failed; diagnostics 100/100

## Log

### 2026-07-03 — CEO
Created from ORGANISM WS5 COCKPIT decomposition (/daslab-plan). Spec-of-record: docs/research/ORGANISM-PROGRAM-PLAN.md.
READ: scripts/cockpit.py, scripts/trends.py, scripts/wave_kpi.py, scripts/cost/cost_ledger.py, scripts/metrics_lib.py, board/interrupts/README.md.
Scope+acceptance (expand; keep frontmatter exact): GATE-3 (P17). EXTEND scripts/cockpit.py render()/panels IN PLACE (reuse NODATA + _render_panel): add panels for live run feed, wave timeline, per-agent success/tokens/tier, per-tool usage, budget burn (cost-ledger), and T1-T7 sparklines (trends.py). Add an ACTION CONSOLE panel listing pending interrupt-cards (board/interrupts/) with copy-paste answer stubs (so the Founder can answer in <60s). Every §5 contract number (T1-T7, spans, cost) visible. Data from the event store + cost-ledger; NODATA when empty. Tests.
Acceptance: [ ] new panels: run-feed/wave-timeline/per-agent/per-tool/budget/T-sparklines; [ ] Action Console with interrupt-cards + answer stubs; [ ] reuses NODATA/_render_panel (no second cockpit); [ ] every §5 number visible; [ ] full suite 0 failed, diagnostics 100/100.
Constraints: org-engine, NO project: field.

### 2026-07-03 — Frontend EM
Extended `scripts/cockpit.py` `render()` IN PLACE (reused `NODATA` + `_render_panel`; no second cockpit) with seven new panels appended after the six base health panels:
- Live Run Feed — T1 busy fraction + run_start/run_end counts + last N runs (event store).
- Wave Timeline — T3 concurrency + per-wave dispatched sparkline + recent waves (wave-log + events).
- Per-Agent Usage — per-agent success / tokens / tier rolled up from span events.
- Per-Tool Usage — tool_call names + span-kind mix + tool_unavailable count.
- Budget Burn — cost-ledger (`cost.cost_ledger.aggregate_spans`): total spans, est USD, tokens, per-tier cost; unpriced tiers surfaced.
- Metrics T1-T7 & Sparklines — every §5 number (T1 busy, T2 idle, T3 concurrency, T4 haiku share, T5 recovery, T6 rework, T7 rubric) in one glance + a throughput sparkline via `trends.py`.
- Action Console — lists every pending `board/interrupts/<id>.json` card (skips `schema.json`) with its question/options and a copy-paste `resume:<option>` stub per option (<60s Founder answer). Malformed/unreadable cards annotated, never fatal.
Every panel degrades to `NODATA` (or an honest empty-state line for the console) — no fabrication, no crash. Added `--interrupts` arg (default `board/interrupts`). Did NOT touch `scripts/cockpit_html.py` (DAS-1482 owns it this wave).
Tests: added 18 cases to `tests/test_cockpit.py` covering every new panel populated + empty/NODATA, schema.json exclusion, malformed-card survival, and full-render surfacing.
VERIFY (FULL, in worktree): `python3 -m pytest -q` → 1425 passed, 1 skipped, 0 failed; `python3 scripts/diagnostics.py` → 100/100; `python3 scripts/board_lint.py` → 0 violations; `ruff check scripts tests` → clean.
Committed LOCAL-only on branch `feat/das-1481-cockpit-panels` (commit 1b85953); no push/PR per dispatch. Handing to CTO (my reviewer per ROUTING) for GATE-3 review.

### 2026-07-03 — Orchestrator (/daslab-cycle collect)
Done. extended cockpit.py to 13 panels (run-feed/wave-timeline/per-agent/per-tool/budget-burn/T1-T7-sparklines) + Action Console (interrupt-cards + copy-paste resume stubs); every §5 number visible; NODATA on empty.
