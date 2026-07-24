---
id: DAS-1541
title: MUSTAQIL order-0 prep — retrieval ADR + program bootstrap (EPIC)
status: backlog
assignee: cto
author: ceo
dept: engineering
priority: p1
parent: 
goal: mustaqil-prep-retrieval-adr
created: 2026-07-23
updated: 2026-07-23
---

## Description

**EPIC — MUSTAQIL v3.0 order-0 prep.** Cross-cutting bootstrap that unblocks every
workstream A–H. NOT a full six-stage AADL cycle (it is program scaffolding + one
ADR); the per-workstream AADL applies to A–H.

Two outcomes:
1. **Retrieval-strategy ADR** — ratify agentic-search-first (grep / Read /
   CONTEXT-PACK / ArcRift recall) as the default; define the vector-DB escape-hatch
   criteria (a large-repo metric must justify it AND this ADR must approve it); the
   index is NEVER the source of truth (board stays canonical, C2). Founder answer Q11.
2. **Program bootstrap** — conservative `budgets.yaml` caps (per-run / per-day; the
   Claude-subscription monthly credit is the outer ceiling, ADR-0027 SI-5), a
   feature-flag scaffold for the WS-A…H keys in `config/features.yaml` (all DEFAULT
   OFF, ADR-0019), and a TN-1 in-tenant precondition check (any hosted/external
   endpoint carrying code/IP is a config error that BLOCKS a run).

**Source of record:** `APPROVED-GOAL-QUEUE.md` order 0 · master prompt v3.0
(`docs/research/2026-07-23-daslab-mustaqil-master-prompt-v3.md` Part 2) · discovery
answers Q3/Q9/Q11.

**Children:** DAS-1542 (retrieval ADR), DAS-1543 (bootstrap).

## Acceptance criteria
- [ ] DAS-1542 and DAS-1543 both `done` with green CI.
- [ ] Retrieval-strategy ADR merged (Accepted), encoding agentic-search-first + the vector-DB escape-hatch criteria + C2 (index never source of truth).
- [ ] `budgets.yaml` present with conservative caps; a wave that would breach a cap evaluates to idle + alert (SI-5); the monthly-credit ceiling is documented.
- [ ] Feature-flag scaffold present in `config/features.yaml` for the WS-A…H keys, all DEFAULT OFF; read via `scripts/feature_flags.py`.
- [ ] TN-1 in-tenant precondition check exists and BLOCKS on a hosted/external code/IP endpoint.
- [ ] `diagnostics.py` 100/100; `board_lint` green; no `project:` field (R9).

## Log
### 2026-07-23 — CEO
Created by /daslab-plan from the Founder-approved MUSTAQIL v3.0 queue (order 0). Org-engine epic — no `project:` field (board_lint R9).
