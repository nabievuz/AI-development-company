---
id: DAS-1489
title: Learned-instructions distillation loop in daslab-learn
status: done
assignee: cpo
author: ceo
dept: engineering
priority: p1
parent: DAS-1484
goal: organism-ws6-guild
zone: daslab-learn
created: 2026-07-03
updated: 2026-07-03
---

## Description

**What.** Extend the existing `skills/daslab-learn` skill with a DISTILLATION
step that closes the learning loop: accepted Founder feedback is distilled into a
role's template `## Learned` section (bounded, deduplicated, dated) and the agent
is regenerated from that template. Many low-level learnings are clustered/merged
into durable, higher-confidence insights; a narrow role-scoped insight may be
promoted to org scope under a manager gate.

**Why.** Today Founder feedback is captured as per-record learnings but never
consolidated back into the durable agent templates, so agents relearn the same
lessons. A distillation loop turns transient feedback into permanent, versioned
role instructions — the organism's memory-to-behavior write path (ORGANISM WS6
GUILD, P20, GATE-3).

**Embedded context.** Spec-of-record is `docs/research/ORGANISM-PROGRAM-PLAN.md`.
This ticket implements the WS6 GUILD "learned-instructions distillation" node.
The existing `daslab-learn` trust model already governs what may be read/written
per project (per-project read-write / read-only / deny) and attaches a per-record
confidence score. Distillation MUST reuse this model — the higher-confidence
insight it produces feeds the SAME trust/confidence machinery. The workstream
`deny-boundary` is a hard wall: distillation must never move a learning across a
project's deny boundary (no cross-project leakage of learned instructions).

**Extend vs new.** EXTEND `skills/daslab-learn` and `scripts/memory_lib.py`; do
NOT fork the trust model or create a parallel learning subsystem. The distillation
step is a new stage layered onto the existing skill's read/write/confidence
plumbing.

**Key files + paths.**
- `skills/daslab-learn/SKILL.md` — skill definition; add the distillation step.
- `scripts/memory_lib.py` — trust model + per-record confidence; extend for
  cluster/merge and the promotion (narrow→org) manager gate.
- Role templates carrying the `## Learned` section (regen source for agents).
- `scripts/gen_subagents.py` — agent regeneration from templates.
- `docs/research/ORGANISM-PROGRAM-PLAN.md` — spec-of-record.

## Acceptance criteria

- [x] `daslab-learn` distillation step: accepted Founder feedback → role template
  `## Learned` section (bounded, deduplicated, dated) → regenerated agent.
- [x] Reuses the existing daslab-learn trust model (per-project read-write /
  read-only / deny + per-record confidence) — extend, not fork; honors the
  workstream deny-boundary (distillation never crosses it).
- [x] Clusters/merges many low-level learnings into a durable higher-confidence
  insight; narrow→org promotion is gated behind a manager gate.
- [x] Round-trip (feedback → `## Learned` → regen agent) demonstrated on 2 roles.
- [x] Tests added; full suite 0 failed, diagnostics 100/100.

## Log

### 2026-07-03 — CEO
Created from ORGANISM WS6 GUILD decomposition (/daslab-plan). Spec-of-record: docs/research/ORGANISM-PROGRAM-PLAN.md.
READ: skills/daslab-learn/SKILL.md, scripts/memory_lib.py.
Scope+acceptance (expand; keep frontmatter exact): GATE-3 (P20). Extend skills/daslab-learn with a DISTILLATION step: accepted Founder feedback -> appended to the role's template ## Learned section (bounded, deduplicated, dated) -> regenerated agent. Reuse the existing daslab-learn trust model (per-project read-write/read-only/deny + per-record confidence) — extend, do NOT fork; respect the workstream deny-boundary (distillation must not cross it). Cluster/merge many low-level learnings into a durable higher-confidence insight; promote narrow->org under a manager gate. Demonstrate the round-trip on 2 roles. Tests.
Acceptance: [ ] daslab-learn distillation step (Founder feedback -> ## Learned, bounded/deduped/dated -> regen agent); [ ] reuses trust model + honors deny-boundary; [ ] round-trip demonstrated on 2 roles; [ ] full suite 0 failed, diagnostics 100/100.
Constraints: org-engine, NO project: field.

### 2026-07-03 — Product Analyst
Implemented P20 distillation loop. All acceptance criteria met.

Files changed:
- `scripts/memory_lib.py` — added 9 distillation functions: `_record_confidence`, `cluster_learnings`, `merge_cluster`, `distill_learnings`, `is_org_promotion`, `needs_manager_gate`, `format_learned_section`, `apply_learned_to_template`. Also exported `MAX_LEARNED` (10) and `CLUSTER_THRESHOLD` (0.60) constants. Extends existing trust + confidence machinery; reuses `jaccard()`, `recallable()`.
- `skills/daslab-learn/SKILL.md` — added "## Distillation (P20)" section: 9-step pipeline description + idempotency + hard rules (deny-boundary, manager gate, MAX_LEARNED cap).
- `engineering/agents/backend-eng-1/AGENTS.md` — round-trip demonstration: added `## Learned` section with 2 distilled insights (build-before-test, full-turbo-build-gate).
- `product/agents/product-analyst/AGENTS.md` — round-trip demonstration: added `## Learned` section with 2 distilled insights (metric-denominator-check, rollback-first-policy).
- `tests/test_learned_distillation.py` — 42 new tests covering all distillation functions + 2 role round-trips + deny-boundary enforcement + manager-gate detection + live overlay file assertions.

Verification: `python3 -m pytest -q` → 1483 passed, 1 skipped (0 failed); `python3 scripts/diagnostics.py` → 100/100; `python3 scripts/board_lint.py` → 0 violations; `ruff check scripts tests` → all checks passed.

Agent shims regenerated: `python3 scripts/gen_subagents.py` → 32 roles + board/ROUTING.md.

Handing off to CPO for review (assignee: cpo per ROUTING.md).

### 2026-07-03 — Orchestrator (/daslab-cycle collect)
Done via local-only done-gate: full suite 1494 + validators (union-merge resolved). daslab-learn distillation loop (9 fns in memory_lib + ## Distillation, bounded/deduped/dated, MAX_LEARNED=10, deny-boundary honored) + round-trip demo on backend-eng-1 + product-analyst; 42 tests.
