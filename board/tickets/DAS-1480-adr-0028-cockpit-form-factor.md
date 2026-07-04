---
id: DAS-1480
title: Author ADR-0028 cockpit form-factor
status: done
assignee: chairman
author: ceo
dept: engineering
priority: p1
parent: DAS-1479
goal: organism-ws5-cockpit
zone: docs/adr
created: 2026-07-03
updated: 2026-07-03
---

## Description

GATE-1 Planning ticket for the ORGANISM WS5 COCKPIT workstream. Author a new
Architecture Decision Record, `docs/adr/0028-cockpit-form-factor.md`, that
decides the delivery form-factor for the DasLab cockpit view.

**What:** Decide (per spec §9 default #4) a **zero-infra, local,
auto-refreshing HTML** cockpit rendered from the event store + cost-ledger.
The ADR must pick and justify ONE of:
- a stdlib `http.server`-based local server that regenerates on request, OR
- a static-regeneration approach (regenerate an HTML snapshot on demand/on a
  tick) that opens as a plain file.

**Hard constraints the decision must honor:**
- NO external services (no hosted dashboards, no third-party analytics).
- NO JavaScript build step (no bundler, no npm toolchain).
- Must **degrade gracefully to a static snapshot** when live regeneration is
  unavailable.

**Extend-vs-new (binding):** This EXTENDS the existing cockpit renderer —
`scripts/cockpit.py`'s `render()` / `_render_panel` / `NODATA` path. It must
NOT introduce a second cockpit implementation. The ADR records that the HTML
form-factor is a rendering target layered onto the current renderer, reusing
its panel/NODATA semantics.

**Why:** WS5 needs a decided, sourced form-factor before any cockpit HTML work
is dispatched (GATE-1 must close first). This ADR is the spec-of-record for
downstream WS5 tickets.

**Key files + paths:**
- New: `docs/adr/0028-cockpit-form-factor.md` (highest existing ADR is 0027;
  you author 0028).
- Update: `docs/adr/README.md` — add the index row for ADR-0028, following the
  existing table theme/format.
- Reference (read, extend — do not fork): `scripts/cockpit.py`
  (`render()`, `_render_panel`, `NODATA`), `scripts/trends.py`.
- Spec-of-record: `docs/research/ORGANISM-PROGRAM-PLAN.md` (§9 default #4).

## Acceptance criteria

- [x] `docs/adr/0028-cockpit-form-factor.md` authored (merge pending review).
- [x] `docs/adr/README.md` index row added for ADR-0028 (matching table theme + WS5 theme paragraph).
- [x] Zero-infra local HTML form-factor decided AND justified (static-regeneration-first
      picked over server-first; optional stdlib `http.server` live mode; rationale in D-1/D-3).
- [x] NO external services and NO JS build step in the decided approach (D-2/D-6).
- [x] Graceful degrade-to-static-snapshot documented as part of the decision (D-5 — structural base case).
- [x] ADR explicitly states it EXTENDS `scripts/cockpit.py`
      (`render()`/`_render_panel`/`NODATA`) and does not replace it / add a
      second cockpit (D-4).
- [x] `diagnostics 100/100`.

## Log

### 2026-07-03 — CEO
Created from ORGANISM WS5 COCKPIT decomposition (/daslab-plan). Spec-of-record: docs/research/ORGANISM-PROGRAM-PLAN.md.
READ: docs/adr/README.md, scripts/cockpit.py, scripts/trends.py.
Scope+acceptance (expand; keep frontmatter exact): GATE-1 Planning. Author docs/adr/0028-cockpit-form-factor.md deciding (§9 default #4): zero-infra local auto-refreshing HTML rendered from the event store + cost-ledger (stdlib http.server OR static regen — pick + justify), NO external services, NO JS build step, degrade gracefully to a static snapshot. It EXTENDS scripts/cockpit.py's render()/_render_panel/NODATA — never a second cockpit. README index row + theme (highest ADR is 0027; you author 0028).
Acceptance: [ ] ADR-0028 merged + README row; [ ] zero-infra local HTML form-factor decided + justified; [ ] degrade-to-static; [ ] extends cockpit.py not replaces; [ ] diagnostics 100/100.
Constraints: org-engine, NO project: field.

### 2026-07-03 — CTO
Authored `docs/adr/0028-cockpit-form-factor.md` (GATE-1 Planning, RACI 3.1 A). Decision:
zero-infra local HTML, **static-regeneration-first** (canonical = a self-contained `file://`
snapshot, the default shipped state) with an **OPTIONAL** stdlib `http.server` live mode
(loopback-only, foreground, operator-invoked, regenerate-on-request). Chose static-first over
server-first because it (a) aligns with the "NOT a daemon" law shared with ADR 0027, (b) has
zero moving parts (`file://`, no port/bind/firewall), and (c) makes degrade-to-static
**structural** — the static file is the base case, the server is the extension, so the fallback
path is exercised on every ordinary use, not only in an emergency. Six binding invariants
D-1…D-6: static-regen canonical; auto-refresh via `<meta http-equiv="refresh">` (NO JS at all —
strictest reading of "no JS build step"); optional loopback stdlib server; **EXTENDS**
`cockpit.py` `render()`/`_render_panel`/`NODATA` (the `cockpit_html.py` wrapper of DAS-1482
imports the panel data-binding funcs — one cockpit, two skins, never a second cockpit);
structural degrade-to-static with generated-at timestamp + inherited `NODATA` non-fabrication;
self-contained single artifact (inline CSS, no CDN/font/analytics/`fetch`). Added the README
index row (#0028) and a WS5 theme paragraph, matching table theme/format.
Numbering: plan text says "ADR-0027" but 0026/0027 were already taken (communication-flows,
scheduler-safety); README ledger is authoritative → this is **0028** (confirmed by DAS-1479/1482
references).
VERIFY (FULL, in worktree): `pytest` 1408 passed / 1 skipped (0 failed); `diagnostics.py`
100/100 (8/8 buckets); `board_lint.py` 0 errors; `check_comm_flows.py` clean. No `project:`
field (board_lint R9 clean). Committed LOCAL-ONLY on branch `feat/das-1480-adr-0028-cockpit`
(strict no-push per dispatch).
Handoff: status → `in_review`, assignee → **chairman** (author is `ceo`; per ROUTING the
author's manager can't review own work — escalate one level above CEO → Chairman; NOT ceo).
Downstream WS5 builds against D-1…D-6: O5-T02 panels (frontend-em), O5-T03 Action Console
(DAS-1481), O5-T04 HTML wrapper `cockpit_html.py` (DAS-1482).

### 2026-07-03 — Chairman of the Board
GATE-1 sign-off review (author=ceo → escalated one level above CEO to Chairman per ROUTING; not
reviewing own work). VERDICT: **PASS**.
Verified against acceptance + GATE-1:
- Zero-infra local HTML decided AND justified — static-regeneration-first canonical (`file://`
  self-contained snapshot, default shipped state; D-1) chosen over server-first with sound
  three-part rationale (NOT-a-daemon law shared w/ ADR 0027; zero moving parts; structural
  degrade). Optional stdlib `http.server` live mode is loopback-only, foreground,
  operator-invoked, regenerate-on-request, no daemon lifetime (D-3).
- NO external services / NO JS build step — auto-refresh is `<meta http-equiv="refresh">`, no
  JavaScript at all; no CDN/font/analytics/`fetch`; pure-Python-stdlib (D-2/D-6).
- Degrade-to-static is STRUCTURAL, not a bolted-on path — static file is the base case, server is
  the extension; generated-at UTC timestamp makes staleness honest; non-fabrication inherited
  from cockpit.py `NODATA` / trends.py `insufficient` (D-5).
- EXTENDS `scripts/cockpit.py` `render()`/`_render_panel`/`NODATA` — confirmed the seam exists
  (cockpit.py L62 NODATA, L187 `_render_panel`, L193 `render`); wrapper `cockpit_html.py`
  (DAS-1482) imports the panel data-binding funcs, one cockpit two skins, never a second
  cockpit; this ADR edits no runtime code (D-4).
- Invariants D-1…D-6 sound and internally consistent; Consequences (positive + accepted
  negatives) and Law check (RACI/AADL/board-audit/project-placement/model-allocation) all hold.
- Numbering correct: 0028. Plan text says "0027" but README ledger (authoritative, append-only)
  already assigned 0026 communication-flows / 0027 scheduler-safety; DAS-1479/1482 already
  reference 0028. Numbering note in the ADR documents this.
- README: index row #0028 present with resolving link + WS5 COCKPIT theme paragraph, matching
  table theme/format.
Gates re-run on MAIN (local): `diagnostics.py` **100/100** (8/8 buckets); `board_lint.py` **0
violations** (43 tickets; R9 clean — no `project:` field); `pytest -q` **1408 passed / 1 skipped
/ 0 failed**.
Disposition: acceptance criteria satisfied, GATE-1 Planning for WS5 form-factor CLOSED. status →
`done`. Committed LOCAL-ONLY (strict no-push per dispatch).
