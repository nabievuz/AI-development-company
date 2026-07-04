---
id: DAS-1540
title: R6 — document the token-usage collect-step wiring for live cost
status: done
assignee: tech-writer
author: cpo
dept: product
priority: p2
created: 2026-07-04
updated: 2026-07-04
---

## Goal

Close the last R6 gap: document exactly how the `/daslab-cycle` **collect step**
must populate real per-dispatch token usage into the wave's records, so live
waves emit non-zero span tokens and the R6 chain fills real dollars end to end:

`token_usage.parse_usage` → `DispatchRecord` token fields → span
`gen_ai.usage.*` + `run_end.token_total` → `check_spans` reconcile + `cost_ledger`
pricing.

## Deliverable

A short, accurate design note at `docs/research/2026-07-04-r6-collect-wiring.md`
covering:

- where the collect step obtains each agent's usage block
  (`input_tokens` / `output_tokens` / `cache_read_input_tokens` /
  `cache_creation_input_tokens`);
- calling `scripts/token_usage.usage_token_fields(usage)` to map it to the three
  span buckets;
- the exact `DispatchRecord` fields to set
  (`input_tokens` / `output_tokens` / `cached_input_tokens`);
- the Truth-Oath rule: unknown usage → `0`, never fabricated; a malformed count
  raises rather than coercing garbage into a dollar figure.

## Definition of Done

- The note exists and is accurate against `scripts/token_usage.py` and
  `scripts/dispatch_emitter.py` (no code changes required — doc only).
- No `git push` / `gh pr` (gated build — local only).

## Log

### 2026-07-04 — Technical Writer

Wrote docs/research/2026-07-04-r6-collect-wiring.md covering the complete token-usage collect-step wiring: source (agent usage blocks), parser (usage_token_fields), DispatchRecord token fields, downstream span/run_end threading, Truth-Oath rule (zero vs. error), complete example, and R6 wiring gate checklist. Accurate to scripts/token_usage.py and scripts/dispatch_emitter.py as of commit a9370e7.
