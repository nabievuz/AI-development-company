---
id: DAS-1647
title: Wire mcp__imagegen cost metering into budgets.yaml with a real mechanical ceiling
status: in_review
assignee: coo
author: security-lead
dept: operations
priority: p1
parent: 
goal: platform-hardening
labels: [governance, cost]
zone: config
depends_on: []
created: 2026-08-04
updated: 2026-08-04
---

## Description

**Routed out of DAS-1645's security sign-off, where it was upgraded from a note to a
hard gate.** The reviewer accepted the current `mcp__imagegen` grant but refused the
cost criterion, and `governance/policies/third-party-model-tools.md` §5 now blocks
widening the grant to any further role until this lands.

`config/budgets.yaml` prices Claude tiers per 1M tokens. A third-party image call is
priced **per image**, not per token, so the file has no home for the line — and
nothing anywhere caps the number of calls or the spend they produce.

**Why this is different from every other cost line in the org.** Every prior spend
path bills Anthropic tokens the SI-5 rails already meter. This one bills a real
external account through `OPENROUTER_API_KEY`. Today the only thing bounding it is
**social** — the grant names three design roles — not mechanical. A retry loop in a
design wave bills that account and no control in this repo stops it.

The reviewer was explicit that this does **not** block the current grant: the blast
radius is three roles, and the account carries its own credit ceiling. It blocks
*widening*. Treat it as bounded, not urgent.

## Acceptance criteria
- [x] `config/budgets.yaml` gains a representation for per-call (non-token) third-party
      spend — decide and record whether that is a new section or a generalisation of
      the existing shape; do not bend a per-1M-token field into meaning something else.
- [x] A real mechanical ceiling exists: calls and/or spend are capped, and exceeding
      the cap denies rather than warns.
- [x] `scripts/check_cost.py` reads the new line and fails when the ceiling is breached
      — proven by probe, both directions (under the cap passes, over it denies).
- [x] Per-image pricing for both models in `_ALLOWED_MODELS` recorded with its source
      and the date read, since provider prices move.
- [ ] `governance/policies/third-party-model-tools.md` §5 updated to reflect that the
      widening block is lifted, once and only once the ceiling is mechanically enforced.
      **NOT checked — see log: block deliberately left in place, partial delivery.**
- [x] `diagnostics.py` 100/100 *(N/A this wave — repo baseline is 85/100 due to
      DAS-1646, unrelated and being fixed in parallel; confirmed unchanged by this
      ticket's diff)*; `board_lint`/validators green; no flag flipped; no
      `project:` field (R9).

## Log
### 2026-08-04 — orchestrator (daslab-cycle wave)
Filed on the explicit routing request in `security-lead`'s DAS-1645 sign-off report.
Assigned to `finance-analyst` (budgets/spend rails are Operations' RACI area) with
`security-lead` as author — the reviewer who set the gate should see how it is closed.
Zone `config`, deliberately disjoint from DAS-1648's `tools/mcp_bridges`, so the two
imagegen follow-ups can run in the same wave without tripping the zone guard.

### 2026-08-04 — Finance / Billing Analyst

**Delivered, zone `config` + `scripts/check_cost.py` only:**

- `config/budgets.yaml`: new `third_party_tools.imagegen` section — a NEW
  section, not a `tiers:` generalisation (recorded rationale in the file: a
  per-1M-token field must not be bent to mean per-image, or a reader can no
  longer trust what unit a number is in). Contains per-image pricing for both
  `_ALLOWED_MODELS` ids (`google/gemini-3-pro-image-preview` = $0.134/image,
  `google/gemini-2.5-flash-image` = $0.039/image), each with `source` +
  `source_read_date: 2026-08-04`
  (`https://ai.google.dev/gemini-api/docs/pricing`, fetched live this session),
  and a `caps.per_day` ceiling (`max_calls: 40`, `max_cost_usd: 6.00`,
  `on_breach: deny`).
  **Pricing caveat, recorded in-file and worth repeating here:** the sidecar
  calls these models THROUGH OpenRouter, not Google's direct API.
  OpenRouter's own model pages (fetched live, 2026-08-04) publish only token
  pricing for both ids (`$2/$12 per 1M` and `$0.30/$2.50 per 1M`
  respectively) — no per-image figure — and those token rates do NOT match
  Google's direct-API rate, so it is not a simple pass-through. I used
  Google's direct-API per-image list price as the best available documented
  figure and said so explicitly rather than inventing an OpenRouter-specific
  number; re-verify against a real OpenRouter invoice before relying on this
  for anything tighter than the conservative per_day cap.
- `scripts/check_cost.py`: added `--check-imagegen` (independent of the
  token-ledger path — a genuinely different subsystem, see the inline
  comment), `evaluate_imagegen_ceiling()` (pure, denies on breach — not a
  warning), and two ways to feed it: `--imagegen-model` + `--imagegen-calls`
  (direct probe, no event store needed) and reading real `span` events from
  the DGO-X store filtered to today (UTC) and to the reviewed model ids.
  **Proven by probe, both directions, both ways:**
  - Probe mode: 10 calls of the cheap model → exit 0 (OK); 50 calls → exit 1
    (DENY: calls 50 > cap 40); 45 calls of the expensive model → exit 1
    (DENY on both calls AND cost); an unpriced model id → counted toward
    calls, excluded from cost, flagged explicitly, still exit 0 under cap.
  - Real-event mode: built synthetic `span` events via `dgox.events.build_span`
    (5 calls → exit 0 OK; 45 calls of the pricier model → exit 1 DENY) —
    exercised the actual `iter_events`/`parse_created_at` path, not just the
    probe shortcut.
- `governance/policies/third-party-model-tools.md` §5: added a dated status
  note. **Did NOT lift the widening block** — see below.

**Why the block stays in place (per explicit instruction: partial work keeps
the block).** Two real gaps outside this ticket's zone:
1. `tools/mcp_bridges/imagegen_tool_bridge.py` does not call
   `check_cost.py --check-imagegen` before sending a request, and emits no
   `span` event after one — so the mechanism exists but nothing invokes it at
   the moment a real call happens. That file is DAS-1648's zone, not touched.
2. `--check-imagegen` is not wired into any automatic gate (e.g.
   `diagnostics.py`, also out of zone — DAS-1646). It has to be invoked by a
   human or CI step today.
   So today, real traffic never breaches the ceiling because no span is ever
   emitted for an imagegen call — only the probe mode and a hand-built event
   file exercise the deny path. The pricing and the deny LOGIC are real and
   provable; they are not yet load-bearing at call time.

**Verification:** full suite `python3 -m pytest -q` → 2755 passed, 3 skipped,
0 failed (includes `tests/test_cost_ledger.py`, `tests/test_alerting_cost.py`,
`tests/test_imagegen_tool_bridge.py` — none of which I edited, all green).
`scripts/board_lint.py` → OK, 208 tickets, 0 violations (one pre-existing
unrelated WARN on DAS-1507). `ruff check scripts/check_cost.py` → clean.
`scripts/diagnostics.py` → 85/100, unchanged from the stated pre-existing
DAS-1646 baseline (not my zone, not touched).

**Follow-up to route (I cannot spawn tickets/agents — flagging for the
orchestrator):** a ticket is needed to (a) instrument
`tools/mcp_bridges/imagegen_tool_bridge.py` to emit a `span` event per call
(or call `check_cost.py --check-imagegen` pre-flight) and (b) wire
`--check-imagegen` into an automatic gate. Only after both land should §5's
widening block actually be lifted.

Committed and pushed to `feat/das-1647-imagegen-cost-ceiling` (pre-existing
worktree branch, tracking `origin/feat/das-1647-imagegen-cost-ceiling`).
`gh` CLI is not installed in this worktree environment, so the PR could not be
opened from here — GitHub's push output gave the manual PR-creation link:
`https://github.com/nabievuz/daslab/pull/new/feat/das-1647-imagegen-cost-ceiling`.
Flagging this so the orchestrator/COO can open the PR (or re-run `gh pr create`
where `gh` is available) before treating `done` as reachable. Status →
`in_review`, assignee → `coo` (per `board/ROUTING.md`, my reviewer).
