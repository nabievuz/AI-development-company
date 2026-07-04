---
id: DAS-1468
title: Validate produces-consumes graph in check_dependency_graph
status: done
assignee: backend-em
author: ceo
dept: engineering
priority: p1
parent: DAS-1463
goal: organism-ws2-loom
depends_on: [DAS-1467]
zone: dep-graph
created: 2026-07-03
updated: 2026-07-03
---

## Description

**What & why (GATE-3 / P8).** `scripts/check_dependency_graph.py` today validates
only the *structural* `depends_on:` / `zone:` frontmatter: no dangling deps, an
acyclic `depends_on` graph (via the 3-colour DFS in `_find_cycle`), a well-formed
`zone:`, and the `defer: true ⇒ non-empty depends_on` fanout invariant. It does
**not** understand the ORGANISM WS2 LOOM *dataflow* contract: a wave plan can
declare that a ticket **consumes** an artifact that no other ticket ever
**produces**, and the plan still passes. That is a silent defect — a consumer
whose input never materialises can never become actionable.

This ticket extends the checker so a wave plan **FAILS** when:
1. a ticket's `consumes:` schema names a producer/artifact that **no** ticket on
   the board `produces:`, and
2. the ticket dependency graph is **disconnected or cyclic**.

**Embedded context — the file as it stands.**
- `_fm_field(text, key)` reads a single scalar frontmatter field; list fields like
  `depends_on` are parsed with `DAS_RE.findall` over the raw value. New
  `produces:`/`consumes:` fields will need the same tolerant, no-YAML-dep parsing
  (mirror `_load`, do not add a PyYAML dependency).
- `_load(board_dir)` returns `(deps, zones, files, defers)` — extend the tuple (or
  add a parallel dict) to carry `produces_by_id` / `consumes_by_id`. Keep every
  existing caller working (`scan`, and the `n_with_deps` recompute in `main`).
- `_find_cycle(deps)` is the **existing acyclic 3-colour DFS** — REUSE it for the
  cycle check; do not write a second traversal. "Disconnected" here means the
  `depends_on` graph (undirected connectivity over declared edges) splits into
  more than one component among tickets sharing a `goal:` — surface an actionable
  message naming the orphaned component(s).
- `scan(board_dir)` aggregates `(who, reason)` violation tuples; add the new
  producer/consumer and connectivity violations in the same shape so `main`'s
  reporting and exit codes (0 clean / 1 violation / 2 usage) are unchanged.
- **CI-safe / dormant contract (lines 10-12):** the checker must still PASS when no
  ticket uses `produces:`/`consumes:` — matching today's board state. Only tickets
  that actually declare the fields are subject to the new rule.

**Extend vs new.** EXTEND `scripts/check_dependency_graph.py` in place — do not
create a new script. Add tests to the existing dependency-graph test module (find
it under `tests/` next to the other `check_dependency_graph` coverage; extend it
rather than adding a parallel file).

**Key files.**
- `scripts/check_dependency_graph.py` — the checker to extend (`_load`, `scan`,
  reuse `_find_cycle`).
- `scripts/board_lint.py` — R9 (org board is platform-only; no `project:` field);
  keep this ticket compliant, no `project:`.
- `governance/schemas/` — reference for the `produces:`/`consumes:` frontmatter
  schema shape (align field names/format with the schema of record).
- Spec-of-record: `docs/research/ORGANISM-PROGRAM-PLAN.md` (WS2 LOOM).

## Acceptance criteria

- [x] A consumer whose `consumes:` artifact has **no** matching producer fails with
      an actionable message naming the ticket and the unmatched artifact.
- [x] A ticket whose `consumes:` **is** satisfied by another ticket's `produces:`
      passes.
- [x] A disconnected or cyclic ticket dependency graph fails (cycle detection
      reuses the existing 3-colour DFS `_find_cycle`; disconnection names the
      orphaned component).
- [x] Existing `depends_on` (dangling), `zone:`, and `defer:` checks are unchanged;
      the checker still PASSES on a board with no `produces:`/`consumes:` fields.
- [x] Tests added: missing-producer fails; matched-producer passes; cycle fails.
- [x] Full suite: 0 failed; diagnostics 100/100.

## Log

### 2026-07-03 — CEO
Created from ORGANISM WS2 LOOM decomposition (/daslab-plan). Spec-of-record:
docs/research/ORGANISM-PROGRAM-PLAN.md.
Read scripts/check_dependency_graph.py, scripts/board_lint.py, governance/schemas.
GATE-3 (P8): extend check_dependency_graph so a wave plan FAILS when a consumer's
consumes: schema has no matching producer, or the ticket dependency graph is
disconnected/cyclic. Reuse the acyclic 3-colour DFS already there. Add tests
(missing producer fails; matched producer passes; cycle fails). org-engine,
NO project: field (board_lint R9).

### 2026-07-03 — Backend Engineer 2
Implemented. Branch feat/das-1468-depgraph-pc, commit a9fff8b.

Changes made:
- scripts/check_dependency_graph.py: added _list_field() tolerant reader (mirrors
  board_lint._schema_names_of, no PyYAML dep); extended _load() from a 4-tuple to
  a 7-tuple adding produces_by_id, consumes_by_id, goal_by_id; added two new
  checks in scan(): P/C-1 (every consumes: artifact has a matching produces: on
  the board) and P/C-2 (within a goal group that uses produces/consumes, the
  dataflow-participating tickets must be in the same connected component of the
  undirected depends_on graph — orphaned components named in the error). Both
  checks are CI-safe/dormant when no ticket uses these fields.
- tests/test_check_dependency_graph.py: added _board_pc() helper and 4 new tests:
  test_missing_producer_fails, test_matched_producer_passes,
  test_disconnected_pc_goal_fails, test_board_without_pc_fields_passes.

Results: pytest 1205 passed / 0 failed; diagnostics 100/100; board_lint 0
violations; check_dependency_graph.py clean on live board; ruff clean.
Handing to backend-em for review.

### 2026-07-03 — Orchestrator (/daslab-cycle collect)
Done. check_dependency_graph producer-match + connectivity checks (consumer-without-producer / disconnected dataflow fails).
