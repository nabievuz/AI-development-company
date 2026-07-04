---
id: DAS-1482
title: Zero-infra auto-refresh HTML cockpit with static fallback
status: done
assignee: frontend-em
author: ceo
dept: engineering
priority: p1
parent: DAS-1479
goal: organism-ws5-cockpit
depends_on: [DAS-1480]
zone: cockpit-html
created: 2026-07-03
updated: 2026-07-03
---

## Description

Deliver a zero-infrastructure HTML view of the DasLab cockpit so operators can
watch org/board state in a browser without standing up any external service or
running a JS build. Per ADR-0028 (`docs/adr/0028-cockpit-form-factor.md`), the
cockpit's data-binding lives in `scripts/cockpit.py` and exposes a
`render()`-style entry point; this ticket adds a **NEW** module that consumes
that output and presents it as an auto-refreshing local HTML page, degrading to
a plain static HTML snapshot when no server is available.

**Why:** GATE-3/4 (P17) of the ORGANISM WS5 COCKPIT program requires an
operator-facing, always-current cockpit surface that carries no infra or
toolchain cost. A stdlib-only render keeps the engine self-contained and
avoids adding runtime dependencies.

**Extend-vs-new:** This is a NEW module (e.g. `scripts/cockpit_html.py`). Do
NOT edit `scripts/cockpit.py`'s data-binding functions — import and wrap them.
DAS-1481 owns `scripts/cockpit.py` in this wave; touching it here would create
a merge conflict in the same repo zone.

**Key files + paths:**
- NEW: `scripts/cockpit_html.py` (the HTML wrapper module).
- READ / IMPORT (do not edit): `scripts/cockpit.py` (`render()` and data-binding funcs).
- Spec-of-record: `docs/research/ORGANISM-PROGRAM-PLAN.md`.
- Binding form-factor decision: `docs/adr/0028-cockpit-form-factor.md`.
- Tests alongside the engine's existing test suite.

Implementation must follow ADR-0028 on the render mechanism: either a stdlib
`http.server` that serves an auto-refreshing page, or static regeneration —
whichever ADR-0028 mandates. NO external services, NO JS build step.

## Acceptance criteria

- [x] Auto-refresh HTML page that wraps `scripts/cockpit.render()` output.
- [x] Zero external services; no JS build step (stdlib only, per ADR-0028).
- [x] Graceful degradation to a static HTML snapshot when no server is running.
- [x] Wraps (imports) `scripts/cockpit.py` — does NOT edit its data-binding funcs.
- [x] Tests: renders without a live server; static fallback works.
- [x] Full suite 0 failed, diagnostics 100/100.

## Log

### 2026-07-03 — CEO
Created from ORGANISM WS5 COCKPIT decomposition (/daslab-plan). Spec-of-record: docs/research/ORGANISM-PROGRAM-PLAN.md.
READ: scripts/cockpit.py, docs/adr/0028-cockpit-form-factor.md.
Scope+acceptance (expand; keep frontmatter exact): GATE-3/4 (P17). Build a zero-infra HTML render per ADR-0028: a NEW module (e.g. scripts/cockpit_html.py) that wraps scripts/cockpit.render() output into a local auto-refreshing HTML page (stdlib http.server or static regen — per ADR-0028), NO external services, NO JS build step. Degrade gracefully to a static HTML snapshot when no server. Do NOT edit cockpit.py's data-binding funcs (import + wrap them; DAS-1481 owns cockpit.py this wave). Tests (renders without a live server; static fallback works).
Acceptance: [ ] auto-refresh HTML wrapping cockpit.render(); [ ] zero external services, no JS build; [ ] static-snapshot fallback; [ ] wraps (does not edit) cockpit.py; [ ] full suite 0 failed, diagnostics 100/100.
Constraints: org-engine, NO project: field.

### 2026-07-03 — Frontend Engineer 1
Implemented scripts/cockpit_html.py (NEW module, 320 lines) per ADR-0028 D-1..D-6:
- render_html() pure function: imports cockpit.panel_* data-binding functions (D-4),
  composes them with _render_panel_html() (pure presentation shim), returns a
  self-contained HTML document with inline CSS only (no CDN/font/fetch — D-6).
- <meta http-equiv="refresh" content="N"> auto-refresh; zero JavaScript (D-2).
- write_snapshot() writes board/.cockpit.html on demand; no socket bound (D-1/D-5).
- Optional --serve mode: stdlib socketserver.TCPServer bound to 127.0.0.1 only,
  regenerates on each GET request, foreground/Ctrl-C, NOT a daemon (D-3).
- Generated-at UTC timestamp visible in every snapshot so staleness is honest (D-5).
- board/.cockpit.html added to .gitignore as gitignored runtime state.
- 16 tests in tests/test_cockpit_html.py: renders without server, static fallback,
  no external refs, all six panels, generated-at timestamp, CLI entry point, etc.
- Verification: python3 -m pytest -q → 1424 passed 1 skipped (0 failed);
  python3 scripts/diagnostics.py → 100/100; python3 scripts/board_lint.py → 0;
  ruff check scripts tests → all checks passed.
- Branch: feat/das-1482-cockpit-html; commit 89ef8e4 (LOCAL — STRICT LOCAL-ONLY).
Handing off to Frontend EM for review.

### 2026-07-03 — Orchestrator (/daslab-cycle collect)
Done. cockpit_html.py: static-regen zero-infra HTML (no JS, meta-refresh), optional loopback server, static fallback (16 tests); wraps cockpit.render() (does not edit it).
