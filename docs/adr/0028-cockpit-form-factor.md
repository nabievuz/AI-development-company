# ADR 0028 — Cockpit form-factor (zero-infra local HTML: static-regeneration-first, optional stdlib `http.server` live mode; NOT a daemon)

- **Status:** Accepted (**CTO — decider; RACI 3.1 A (ADR ratifier); AADL GATE-1 Planning artifact — 2026-07-03**)
- **Date:** 2026-07-03
- **Scope:** Platform / org-engine — the delivery form-factor for the ORGANISM operator cockpit (WS5 COCKPIT, O5-T01). A **decision doc only**: it fixes the render/transport contract the WS5 implementation tickets (DAS-1481/DAS-1482, plan O5-T02…O5-T04) must satisfy and ships **no runtime cockpit code**. It does not edit `scripts/cockpit.py`; it names its `render()` / `_render_panel` / `NODATA` seam as the contract the HTML target layers onto.
- **Deciders:** **CTO (accountable)** — ADR/architecture authority (RACI 3.1; IC authors, MGR reviews, CTO ratifies). CEO consulted (WS5 planning owner, ticket author). Frontend-EM consulted (owns the downstream panel + HTML-wrapper implementation, O5-T02…O5-T04). No Founder gate is triggered — this is a decision doc, not a policy/flag mutation.
- **Relates:** ORGANISM WS5 COCKPIT (`docs/research/ORGANISM-PROGRAM-PLAN.md` §4 WS5, §9 Q4 — the approved default #4; §WS5 tickets O5-T01…O5-T04 = DAS-1480…DAS-1482). Cites — but does **not** edit — `scripts/cockpit.py` (the six-panel passive renderer: `render()`, `_render_panel`, `NODATA`), `scripts/trends.py` (T1–T7 trend/sparkline source), `scripts/metrics_lib.py` / `scripts/wave_kpi.py` / `scripts/memory_lib.py` (the panel data sources cockpit.py already imports), `board/.events.jsonl` (the load-bearing event store — ADR 0011/0024/0025 — the live run-feed source) and `scripts/cost/cost_ledger.py` + `config/budgets.yaml` (the cost-ledger / budget-burn source). Builds on ADR 0025 (event store is load-bearing) and shares the "operator-invoked, NOT a daemon" stance of ADR 0027 (scheduler safety).
- **Supersedes / Amends:** nothing. This ADR **constrains by reference** how the existing cockpit renderer is delivered as HTML; it mutates no code and forks no cockpit.

> **Numbering note.** The WS5 plan text (§4 WS5 table, §9 Q4) names this artifact "ADR-0027". The append-only ADR numbering rule (README) already assigned **0026** to *communication-flows* and **0027** to *scheduler-safety* (both Accepted 2026-07-03), so the cockpit form-factor decision takes the next free number, **0028**. Plan-text numbers are indicative; the README ledger is authoritative. Downstream WS5 tickets (DAS-1479 epic, DAS-1482 wrapper) already reference `docs/adr/0028-cockpit-form-factor.md`.

> The cockpit is how a human *reads* the ORGANISM the other workstreams build:
> WS1 runs, WS3 spans, WS4 tempo, WS5's own interrupt Action Console. Before any
> HTML lands we need a merged, referenceable decision on **how the cockpit reaches
> a browser** — a plain file, a served page, or a hosted dashboard — so the
> implementation tickets (O5-T02 panels, O5-T04 HTML wrapper) build **against a
> contract**, not an agent's judgement of the day. This ADR closes GATE-1
> (Planning) for the WS5 form-factor. **No behaviour changes on merge** — the
> terminal cockpit (`python3 scripts/cockpit.py`) is untouched.

## Context

The audit's WS5 fork (§9 Q4) is genuine: the cockpit exists today as a **passive,
terminal, six-panel view** (`scripts/cockpit.py` — "Operator Cockpit v1"), each
panel bound to a REAL data source and degrading to the `NODATA` sentinel where no
live telemetry exists yet (nothing mocked, no number fabricated). WS5 wants that
same state **in a browser, auto-refreshing**, so an operator can watch live runs
and answer an interrupt-card in-flow. The question is *which delivery form-factor*,
and it forks three ways — two of them expensive to get wrong:

- **A hosted dashboard / external service** (Grafana, a SaaS board, third-party
  analytics) — violates the zero-infra + no-external-services constraint, adds an
  operational surface and a data-egress path the platform explicitly refuses.
- **A JS single-page app** (bundler, npm toolchain, a live-updating client) —
  violates the **no-JS-build-step** constraint, adds a toolchain the Python engine
  does not otherwise carry, and couples the cockpit to a frontend build.
- **A stdlib, local, zero-infra HTML render** — the approved default #4. Within it
  a second, narrower fork remains: **serve** the page from a stdlib
  `http.server` that regenerates on request, **or** **regenerate a static HTML
  snapshot** on demand that opens as a plain `file://`. This ADR rules that inner
  fork.

The platform already ships everything the *data* side of this needs; none of it is
invented here:

- **`scripts/cockpit.py`** — the renderer. `render(...)` composes six panels via the
  shared `_render_panel(num, title, lines)` and the `NODATA` sentinel; the panel
  data-binding functions (`panel_current_wave`, `panel_frontier`, `panel_quality`,
  `panel_gate6`, `panel_risk`, `panel_memory`) already read the real sources.
- **`board/.events.jsonl`** — the load-bearing event store (ADR 0011/0024/0025): the
  live run-feed / wave-timeline / span source.
- **`scripts/cost/cost_ledger.py` + `config/budgets.yaml`** — the budget-burn source.
- **`scripts/trends.py`** — the T1–T7 trend/sparkline classifier (P5, trigger-gated;
  reports `insufficient` with no live series, never a fabricated trend line).

The question is not "build a dashboard" — it is "which **transport** carries the
existing render to a browser, at zero infra cost, and how does it degrade when
nothing is serving". This ADR answers that as a closed set of decision invariants.

**AADL stage.** GATE-1 Planning. A decision doc; it ships no runtime cockpit change.

**Extend-vs-new posture (binding).** EXTEND, do not duplicate. The HTML form-factor
is a **rendering target layered onto the existing renderer**, reusing its
panel/`NODATA`/`_render_panel` semantics — **never a second cockpit**. Concretely
the HTML wrapper is a NEW module (`scripts/cockpit_html.py`, DAS-1482) that
**imports and wraps** cockpit.py's data-binding functions and does **not** fork or
re-implement them; cockpit.py's terminal `render()` stays the single source of the
panel content. (DAS-1481 owns edits to `scripts/cockpit.py` this wave; DAS-1482's
wrapper only imports it — the "extend" is a layering, not an in-place rewrite.)

## Decision

The cockpit form-factor is a **zero-infra, local HTML render that is
static-regeneration-first, with an OPTIONAL stdlib `http.server` live mode** (§9
default #4). The static snapshot is the **canonical artifact and the default shipped
state**; the served mode is a thin, operator-invoked convenience over the *same*
pure render. It is **not a daemon**, needs **no external service**, and carries **no
JavaScript build step** (indeed no JavaScript at all). The following are the
**binding form-factor invariants** — the contract every WS5 HTML ticket satisfies,
and the citation any future "how should the cockpit reach the browser?" question
resolves to.

### D-1 — Canonical form-factor: static regeneration to a self-contained HTML file

The primary form-factor is **static regeneration**: a `render_html(state) -> str`
pure function emits one self-contained HTML document, written on demand to a file
(e.g. `board/.cockpit.html`, gitignored runtime state) and opened as a plain
`file://` URL. No port is bound, no process is held, no network listener exists in
the default path.

- **Why static-first over server-first.** (a) It aligns with the platform's
  "**NOT a daemon**" law (shared with ADR 0027) — the shipped, default state is a
  plain file, not a running process. (b) Zero moving parts: `file://` works with no
  port, no bind, no firewall prompt, no "is the server up?" failure mode. (c) It
  makes degrade-to-static **structural, not a bolted-on fallback** (D-5): the static
  file is the *base case*, and the server (D-3) is the extension — so the fallback
  path is exercised on every ordinary use, never only in an emergency.
- The document is **self-contained**: inline CSS only, **no** external stylesheet,
  CDN, web font, remote image, analytics beacon, or `fetch`/XHR/WebSocket to any
  host (D-6). Opening it offline renders identically.

### D-2 — Auto-refresh via `<meta http-equiv="refresh">` — no JavaScript, no build step

"Auto-refreshing" is delivered by a single `<meta http-equiv="refresh"
content="N">` tag in the document `<head>`, **not** by JavaScript.

- This honors the **no-JS-build-step** constraint at its strictest: there is no
  bundler, no npm, and no JS at all — the whole page is static HTML + inline CSS.
- The refresh interval `N` is a plain render parameter (a sensible default, operator-
  overridable). In served mode (D-3) each refresh re-hits the server and triggers a
  fresh regen from the event store + cost-ledger; in file mode (D-1/D-5) each refresh
  re-reads the same on-disk snapshot (honestly stale — see D-5).

### D-3 — Optional stdlib `http.server` live mode (regenerate-on-request), operator-invoked, NOT a daemon

For a live experience, an **optional** mode serves the cockpit from Python's stdlib
`http.server` bound to **loopback** (`127.0.0.1`), regenerating the page from the
current event store + cost-ledger **on each request**.

- It uses **only the standard library** (`http.server` / `socketserver`) — no
  framework, no third-party server, no external service.
- It is **operator-invoked and foreground**: a `--serve` flag the operator runs and
  Ctrl-C stops, the same way a human runs `python3 scripts/cockpit.py`. It is **not
  a daemon** — no self-scheduling, no launchd/cron installed by this repo, no
  background lifetime. (Any cadence, if an operator wants one, lives in an external
  OS entry the operator owns — mirroring ADR 0027 SI-1 — not inside the process.)
- Loopback-only bind: the cockpit surfaces internal org/board/cost state and MUST
  NOT be exposed on a routable interface. No auth layer is added because there is no
  remote surface to protect — the trust boundary is "local machine only".

### D-4 — Extends `cockpit.py` `render()`/`_render_panel`/`NODATA` — never a second cockpit

The HTML form-factor **reuses the existing renderer's semantics** and adds only a
rendering target:

- The HTML wrapper (`scripts/cockpit_html.py`, DAS-1482) **imports** cockpit.py's
  panel data-binding functions and composes their output; it does **not** copy,
  fork, or re-implement the panel logic, the `NODATA` sentinel, or the data sources.
  Panel identity, ordering, titles, and the `NODATA` text remain owned by
  `scripts/cockpit.py`.
- The HTML analogue of `_render_panel` (panel → HTML block) is a **pure
  presentation shim** over the same `(num, title, lines)` a panel already yields — a
  second *skin*, not a second *cockpit*. There is exactly one place that decides
  *what* a panel says (cockpit.py) and a thin place that decides *how it looks in
  HTML* (the wrapper).
- Consequently the terminal cockpit and the HTML cockpit can never drift in content:
  they render from the identical data-binding functions. A new panel added to
  cockpit.py (O5-T02) appears in both surfaces with no wrapper change to its data.

### D-5 — Degrade-to-static is structural; non-fabrication is preserved

Graceful degradation to a static snapshot is **not a separate code path** — it is
the base case of D-1:

- With no server running, the last regenerated `file://` snapshot is a complete,
  readable cockpit. Because it carries a **generated-at UTC timestamp** in the page,
  a stale snapshot is **honestly stale** ("generated at T"), never presented as
  live. `<meta refresh>` in file mode simply re-reads the same file — it does not
  fabricate movement.
- **Non-fabrication is inherited from cockpit.py**: where a panel has no live data it
  renders `NODATA` ("no data yet — appears once live waves run; the loop is in
  shadow mode"). The HTML skin renders that sentinel verbatim; it never invents a
  number, a trend line (trends.py already reports `insufficient`), or a fake live
  tick. An empty event store yields a valid, honest HTML page — the same guarantee
  the terminal cockpit gives.
- The static snapshot MUST be renderable **without ever binding a socket** — i.e.
  the render is a pure function of state, callable in a test with no server (DAS-1482
  acceptance: "renders without a live server; static fallback works").

### D-6 — No external service, no external asset, no JS toolchain (self-contained, single artifact)

The whole form-factor is self-contained and offline-capable:

- **No external service** — no hosted dashboard, no SaaS board, no third-party
  analytics, no telemetry egress. The only data sources are local repo files
  (event store, cost-ledger, board tickets, memory outbox) already read by
  cockpit.py.
- **No external asset** — inline CSS only; no CDN script/stylesheet, no web font, no
  remote image, no runtime network call from the page.
- **No JS build step** — no bundler, no npm/pnpm, no node toolchain enters the
  engine; the engine stays pure-Python-stdlib for this feature.

## Consequences

**Positive.**
- WS5 O5-T02 (panels), O5-T03 (Action Console) and O5-T04 (HTML auto-refresh
  wrapper) build against a **fixed, closed set of six invariants** instead of
  re-deriving the transport per ticket. O5-T04's acceptance ("every §5 number visible
  on it; degrades to a static snapshot") maps directly onto D-2/D-5, and DAS-1482's
  "renders without a live server" test onto D-5.
- The "zero-infra" and "auto-refreshing" goals are reconciled without a daemon, a
  service, or a JS build: cadence is a `<meta refresh>` tag (D-2) and, at most, an
  optional foreground loopback server (D-3) — the default shipped state is a plain
  file (D-1). Deleting the feature is deleting one module + one gitignored HTML file.
- **One cockpit, two skins** (D-4): the terminal and HTML surfaces render from the
  identical data-binding functions, so they cannot drift and there is exactly one
  place that fabricates nothing. `NODATA`/non-fabrication (D-5) is inherited, not
  re-implemented.

**Negative / accepted.**
- The static-first model means the `file://` snapshot is **only as fresh as the last
  regeneration** — a browser tab left open in file mode shows an honest but stale
  timestamp until re-regenerated (or until the operator runs `--serve`). **Accepted**
  — an honest stale timestamp beats a live daemon burning a process; freshness is an
  operator action (re-run / `--serve`), matching the "NOT a daemon" posture. D-5's
  generated-at timestamp makes staleness visible, never misleading.
- `<meta refresh>` (D-2) reloads the whole page rather than diffing (no JS, no
  partial update), so a served refresh re-renders everything each interval. **Accepted**
  — the cockpit is a handful of text panels; a full re-render is cheap, and refusing
  JS is the whole point of the no-build-step constraint.
- The served mode (D-3) is **loopback-only with no auth** and therefore not
  multi-user or remote. **Accepted** — the cockpit is a local operator tool over
  internal state; a remote surface would demand auth + an external service, which the
  zero-infra constraint forbids. If remote viewing is ever needed it is a **new ADR**,
  not a widening of this one.

**Law check.**
- **Charter / RACI** — the CTO is the ADR ratifier (RACI 3.1 A: IC authors, MGR
  reviews, CTO ratifies); this ADR is decided by the CTO, CEO + Frontend-EM consulted.
  It amends no policy — it constrains a delivery form-factor by reference.
- **AADL** — a GATE-1 Planning artifact for ORGANISM WS5; no gate skipped; ships no
  runtime cockpit change. The cockpit is view-only and passive; it never signs a
  gate, never answers an interrupt-card itself (the Action Console, O5-T03, surfaces
  cards for the **Founder** to answer — never-auto-approve preserved).
- **Board audit / governance-as-policy** — no SSOT edited in place (`scripts/cockpit.py`
  untouched by this ADR; the wrapper imports it). No never-auto-approve category is
  triggered (a decision doc, not a policy/flag mutation). Runtime HTML output
  (`board/.cockpit.html`) is gitignored runtime state, consistent with the run-model
  (ADR 0023).
- **Project placement** — a platform-level ADR under `docs/adr/`; no project artifact
  written; the `board/tickets/` ticket carries no `project:` field.
- **Model allocation** — unchanged; CTO on opus per the table.

## Enforcement / acceptance

- This ADR is decided by the **CTO** (RACI 3.1, GATE-1 Planning) and is `Accepted` on
  merge. It adds a row to `docs/adr/README.md` and extends the WS5 theme.
- D-1…D-6 are the contract the WS5 implementation tickets satisfy and their
  acceptance hooks test:
  - **D-1/D-5** — DAS-1482: "renders without a live server; static fallback works" —
    a pure `render_html(state)` callable with no socket bound; an empty event store
    yields a valid, honest page (`NODATA`, no fabricated number).
  - **D-2/D-6** — no JS/npm/bundler enters the engine; the page is static HTML +
    inline CSS with a `<meta http-equiv="refresh">` tag and no external asset.
  - **D-3** — the optional live mode uses only stdlib `http.server`, binds loopback,
    is operator-invoked/foreground, and holds no daemon lifetime.
  - **D-4** — the wrapper imports cockpit.py's data-binding functions (no forked
    panel logic / `NODATA` / second cockpit); terminal and HTML surfaces render from
    the same funcs.
- Any future "should the cockpit be a hosted dashboard / a JS SPA / a remote
  multi-user service / a background daemon?" question resolves to **no** by
  D-1/D-3/D-6. An undeclared form-factor is not in this envelope — so it is not
  permitted; widening it is a new ADR that supersedes this one, never an in-place edit.
