---
id: DAS-1490
title: ArcRift recall-ranking composite score in memory_lib
status: done
assignee: backend-em
author: ceo
dept: engineering
priority: p1
parent: DAS-1484
goal: organism-ws6-guild
zone: memory-lib
created: 2026-07-03
updated: 2026-07-03
---

## Description

GATE-3 (P21) work from the ORGANISM WS6 GUILD program. Today the recall path in
`scripts/memory_lib.py` is a **binary filter** — `recallable()` decides whether a
stored note is eligible using the `jaccard()` similarity proxy and `trust_for()`
trust primitives. It has no notion of *ranking*: two eligible candidates come
back in arbitrary order, and a highly relevant-but-old note is treated the same
as a stale-but-fresh one. This ticket adds a **composite ranking score** on top
of the existing filter so recall returns candidates ordered by usefulness, not
just eligibility.

**Why:** better recall ordering directly improves what an agent sees first at the
start of work (Persistent Memory Law) — the top-k it actually reads. A composite
of *semantic similarity + recency + importance* is the standard memory-retrieval
scoring shape and lets us tune retrieval without touching the eligibility gate.

**Extend, do NOT rewrite:** the `recallable()` filter and its trust semantics stay
exactly as they are. This is a NEW ranking function placed *beside* `recallable()`
that scores the already-eligible (or candidate) notes. Reuse the existing
`jaccard()` (similarity proxy) and `trust_for()` primitives — do not reimplement
them. Composite score = `similarity (jaccard proxy) + recency (half-life decay on
note age) + stored importance`. Keep the weighting explicit and documented so it
is tunable.

Also add a **prune hygiene job** as a plain callable (a function that prunes
stale/low-value memories via the existing `prune_memory` path) that the WS4
HEARTBEAT can schedule. Do NOT wire a live loop or background timer here — expose
only the callable; scheduling is the HEARTBEAT's job.

**Key files/paths:**
- `scripts/memory_lib.py` — target: add ranking fn + prune hygiene callable beside `recallable()`; reuse `jaccard()`, `trust_for()`.
- `CLAUDE.md` — Persistent Memory Law (ArcRift) context.
- Spec-of-record: `docs/research/ORGANISM-PROGRAM-PLAN.md`.

## Acceptance criteria

- [x] recall-ranking fn (similarity + recency half-life + importance) beside `recallable()`
- [x] reuses `jaccard()` / `trust_for()` (no rewrite of the filter)
- [x] prune hygiene callable (schedulable by WS4 HEARTBEAT; no live loop wired)
- [x] ranking test: candidates ordered by the composite score
- [x] A/B test: ranking shows equal-or-better retrieval vs filter-only baseline on sample notes
- [x] full suite 0 failed, diagnostics 100/100

## Log

### 2026-07-03 — CEO

Created from ORGANISM WS6 GUILD decomposition (/daslab-plan). Spec-of-record: docs/research/ORGANISM-PROGRAM-PLAN.md.
READ: scripts/memory_lib.py, CLAUDE.md.
Scope+acceptance (expand; keep frontmatter exact): GATE-3 (P21). Upgrade the recall path in scripts/memory_lib.py: ADD a ranking function alongside the existing recallable() FILTER — composite score = semantic similarity (jaccard proxy) + recency half-life + stored importance. Reuse jaccard() + trust_for() primitives; do NOT rewrite the filter. A prune_memory hygiene job schedulable via the WS4 HEARTBEAT (a callable; do not wire a live loop). Tests: ranking orders candidates by the composite; A/B shows equal-or-better retrieval vs the filter-only baseline on sample notes.
Acceptance: [ ] recall-ranking fn (similarity + recency half-life + importance) beside recallable(); [ ] reuses jaccard/trust_for (no rewrite); [ ] prune hygiene callable; [ ] ranking + A/B tests; [ ] full suite 0 failed, diagnostics 100/100.
Constraints: org-engine, NO project: field.

### 2026-07-03 — Backend Engineer 1

Implemented P21 recall-ranking on branch feat/das-1490-recall-ranking.

Added to `scripts/memory_lib.py` (beside existing `recallable()`, no rewrite):
- `_recency_score()` — half-life decay helper (2^(-age/half_life)).
- `composite_score()` — single-memory scorer: w_sim*jaccard + w_recency*recency + w_importance*importance; weights/half-life tunable via config["ranking"]; falls back to trust_score as importance proxy when no explicit "importance" field.
- `rank_memories()` — sorts eligible memories by composite score descending; designed to compose with `recallable()` as a pipeline.
- `prune_hygiene_candidates()` — pure callable returning (id, reason) pairs for expired/quarantined/low-trust memories; no live loop; schedule via WS4 HEARTBEAT.

Added 11 new tests to `tests/test_memory_governance.py`:
- composite_score high-sim win, recency beats stale, rank ordering, empty-list stability, importance field preference.
- A/B test: 3 irrelevant notes inserted first; ranker surfaces all 3 relevant notes in top-3 (precision@3 = 1.0 vs baseline 0.0).
- prune_hygiene_candidates: expired, quarantined, low-trust, pure-callable, empty-store.

Verification: pytest -q 1452 passed 1 skipped 0 failed; diagnostics 100/100; board_lint 0 violations; ruff clean.

### 2026-07-03 — Orchestrator (/daslab-cycle collect)
Done via local-only done-gate: full suite 1494 + validators (union-merge resolved). memory_lib recall-ranking: composite_score (similarity+recency half-life+importance) + rank_memories + prune_hygiene_candidates beside recallable() (no rewrite); A/B precision@3 1.0 vs 0.0; 11 tests.
