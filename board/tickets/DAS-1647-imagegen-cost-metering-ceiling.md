---
id: DAS-1647
title: Wire mcp__imagegen cost metering into budgets.yaml with a real mechanical ceiling
status: todo
assignee: finance-analyst
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
- [ ] `config/budgets.yaml` gains a representation for per-call (non-token) third-party
      spend — decide and record whether that is a new section or a generalisation of
      the existing shape; do not bend a per-1M-token field into meaning something else.
- [ ] A real mechanical ceiling exists: calls and/or spend are capped, and exceeding
      the cap denies rather than warns.
- [ ] `scripts/check_cost.py` reads the new line and fails when the ceiling is breached
      — proven by probe, both directions (under the cap passes, over it denies).
- [ ] Per-image pricing for both models in `_ALLOWED_MODELS` recorded with its source
      and the date read, since provider prices move.
- [ ] `governance/policies/third-party-model-tools.md` §5 updated to reflect that the
      widening block is lifted, once and only once the ceiling is mechanically enforced.
- [ ] `diagnostics.py` 100/100; `board_lint`/validators green; no flag flipped; no
      `project:` field (R9).

## Log
### 2026-08-04 — orchestrator (daslab-cycle wave)
Filed on the explicit routing request in `security-lead`'s DAS-1645 sign-off report.
Assigned to `finance-analyst` (budgets/spend rails are Operations' RACI area) with
`security-lead` as author — the reviewer who set the gate should see how it is closed.
Zone `config`, deliberately disjoint from DAS-1648's `tools/mcp_bridges`, so the two
imagegen follow-ups can run in the same wave without tripping the zone guard.
