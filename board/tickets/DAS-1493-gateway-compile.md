---
id: DAS-1493
title: Build gateway_compile intake pipeline
status: done
assignee: cto
author: ceo
dept: engineering
priority: p1
parent: DAS-1491
goal: organism-ws7-gateway
depends_on: [DAS-1492]
zone: gateway-compile
created: 2026-07-03
updated: 2026-07-04
---

## Description

**What.** Build `scripts/gateway_compile.py` — the WS7 GATEWAY intake pipeline that
turns a submitted PROJECT-OS-PACK into a set of self-contained STORY TICKETS on the
target project's own board. This is the org-engine machinery that gates every new
project through validation, the Founder discovery gate, research enrichment, the
approved-goal-queue check, and finally story-ticket compilation.

**Why.** Today project intake is manual and inconsistent: packs land with broken
links/placeholders, the Founder discovery gate (>=10 Q&A) can be silently skipped,
and story tickets end up requiring archaeology across the repo before a fresh agent
can act. `gateway_compile` makes intake a single deterministic, gated pipeline so a
project only becomes board tickets after it has provably cleared every QONUN gate.

**Embedded context.** Per the ORGANISM WS7 GATEWAY decomposition, the pipeline runs
these stages in strict order:

1. **Validate pack** — placeholder-lint (no unfilled TODO/`<...>` slots), link
   integrity (every referenced path/URL resolves), and schema conformance against
   the PROJECT-OS-PACK spec. A broken pack is REJECTED with actionable, per-field
   errors (file + field + why + how-to-fix), never a bare traceback.
2. **Discovery gate** — confirm the Founder discovery gate is satisfied: >=10 Q&A
   present OR an explicit Founder waiver. If neither, STOP and GENERATE the missing
   discovery questions (so the operator can take them to the Founder). The gate must
   provably BLOCK — no downstream stage runs while it is open.
3. **Research enrichment** — emit a research-enrichment step whose sourced conclusion
   (market, competitors, regulatory, technical architecture, pricing, SEO/channel,
   risks) is stored ONLY in the project folder.
4. **Approved-check** — verify `APPROVED:`/`TASDIQLANDI:` on the goal queue by WIRING
   the existing `scripts/check_approved_goal_queue.py` (do not reimplement its logic).
5. **Compile story tickets** — write STORY TICKETS into
   `projects/<name>/board-tickets/`. Each ticket is self-contained: embedded context
   excerpt, acceptance criteria, produces/consumes, AADL stage tag, and gate ref — so
   a fresh agent window needs zero archaeology. Every story ticket carries
   `project: <name>` (project board) per the QONUN Project Placement Law.

**Extend vs new.** NEW file `scripts/gateway_compile.py`. It WIRES (imports/invokes)
the EXISTING `scripts/check_approved_goal_queue.py` rather than duplicating the
approved-queue check. Follow the ticket-writing conventions in `board/README.md` and
respect `scripts/board_lint.py` (story tickets go on the project board with a
`project:` field; this engine ticket does NOT).

**Key files + paths.**
- New: `scripts/gateway_compile.py`
- Spec of record: `docs/specs/PROJECT-OS-PACK.md`
- Wired: `scripts/check_approved_goal_queue.py`
- Planning skill: `.claude/skills/daslab-plan/SKILL.md`
- Board conventions + lint: `board/README.md`, `scripts/board_lint.py`
- Program plan: `docs/research/ORGANISM-PROGRAM-PLAN.md`
- Output target: `projects/<name>/board-tickets/`

## Acceptance criteria

- [x] `gateway_compile.py` runs the ordered pipeline: validate -> discovery-gate -> approved-check -> compile-story-tickets.
- [x] A deliberately BROKEN pack is rejected with actionable errors (file + field + fix), not a raw traceback.
- [x] The discovery gate provably BLOCKS when <10 Q&A and no waiver, and GENERATES the missing questions.
- [x] The pipeline WIRES the existing `scripts/check_approved_goal_queue.py` (no reimplementation).
- [x] Compiled story tickets are self-contained (embedded context, acceptance criteria, produces/consumes, AADL stage tag, gate ref) AND project-scoped (`project: <name>`).
- [x] A valid sample pack compiles end-to-end to story tickets.
- [x] Full test suite: 0 failed; diagnostics 100/100.

## Log

### 2026-07-03 — CEO
Created from ORGANISM WS7 GATEWAY decomposition (/daslab-plan). Spec-of-record: docs/research/ORGANISM-PROGRAM-PLAN.md.
READ: docs/specs/PROJECT-OS-PACK.md, scripts/check_approved_goal_queue.py, .claude/skills/daslab-plan/SKILL.md, board/README.md, scripts/board_lint.py.
Scope+acceptance (expand; keep frontmatter exact): GATE-3 (P22). Build scripts/gateway_compile.py intake pipeline per PROJECT-OS-PACK.md: validate pack (placeholder-lint, links, schema) -> check Founder discovery gate (>=10 Q&A present or explicit waiver, else STOP and GENERATE the questions) -> emit a research-enrichment step (sourced conclusion stored in the project folder) -> verify APPROVED:/TASDIQLANDI: on the goal queue (WIRE the existing scripts/check_approved_goal_queue.py) -> compile STORY TICKETS into projects/<name>/board-tickets/: each self-contained (embedded context excerpt, acceptance criteria, produces/consumes, AADL stage tag, gate ref) so a fresh agent window needs no archaeology. Story tickets carry project: <name> (project board) per QONUN Placement Law.
Tests: a deliberately BROKEN pack is rejected with actionable errors; the discovery gate provably BLOCKS; a valid sample pack compiles to story tickets.
Produces: gateway-compile (consumed by DAS-1494/1495).
Constraints: org-engine ticket (this WS7 machinery), NO project: field.

### 2026-07-04 — Backend EM
Built `scripts/gateway_compile.py` (P22) — the WS7 GATEWAY intake pipeline, strict-ordered:
1. **validate** — `validate_pack`: manifest schema against PROJECT-OS-PACK §3.1 (FR-002 required keys; FR-003 name==folder; FR-004 unknown key = warning), canonical AADL doc-tree names (FR-005), placeholder-lint (TODO/FIXME/TBD/`<...>`/`[NEEDS CLARIFICATION]`/UPPER-token), relative-link resolution, and Constitution FR-009 (a `constraints` entry pairing a relaxation verb with an org-law noun is REJECTED; a tightening twin passes). Errors are `PackError(file, field, problem, fix)` — actionable, never a traceback.
2. **discovery-gate** — `check_discovery_gate`: >=10 Q&A pairs OR explicit waiver; else BLOCKS and GENERATES the 13 Founder discovery questions; no downstream stage runs (provable via absent `approved-check`/`compile` stages).
3. **research-enrichment** — `emit_research_enrichment`: writes a deterministic 7-section sourced-conclusion scaffold to `docs/01-planning/RESEARCH-ENRICHMENT.md` — INSIDE the project folder only (QONUN Placement).
4. **approved-check** — WIRES `check_approved_goal_queue._queue_approved` (imported, invoked; not reimplemented). Spy test proves the real call.
5. **compile** — `compile_story_tickets`: parses the queue's prioritized table for `founder_approved`/planned/active goal items, emits 1 epic + 6 AADL-stage story tickets per goal into `projects/<name>/board-tickets/`, each self-contained (embedded mission excerpt, acceptance = that stage's GATE seed, `## Produces / Consumes`, AADL stage tag, gate ref) and carrying `project: <name>` (FR-008). Generated tickets are board_lint-clean (verified in a test that lints them).

Demonstrations in `tests/test_gateway_compile.py` (17 tests, all tmp/scratch dirs — never the org board): BROKEN pack (missing required key; placeholder + dead link; name/folder mismatch; non-canonical doc tree) rejected with actionable errors and no tickets written; discovery gate BLOCKS + generates >=10 questions with no downstream run; unapproved queue blocks at approved-check; valid minimal pack compiles to 7 self-contained project-scoped tickets covering GATE-1…GATE-6; a second different pack (`fleet-router`) compiles with no code change (FR-010); relax-vs-tighten twins (SC-005).

VERIFY (full, in worktree): `python3 -m pytest -q` → 1576 passed, 1 skipped. `python3 scripts/diagnostics.py` → 100/100. `python3 scripts/board_lint.py` → 0 violations (56 tickets). `ruff check scripts tests` → clean. Committed LOCAL only (no push/PR per dispatch).

Routing: → CTO for GATE-3 review (author is ceo; reviewer per ROUTING = manager CTO). Downstream DAS-1494/1495 consume `gateway-compile`.

### 2026-07-03 — Orchestrator (/daslab-cycle collect)
Done via local-only done-gate: full suite 1576; gateway_compile.py pipeline (validate/discovery-gate/research/approved-check/compile), broken-pack rejected + discovery-gate blocks + valid pack -> 7 self-contained tickets; wires check_approved_goal_queue; 17 tests.
