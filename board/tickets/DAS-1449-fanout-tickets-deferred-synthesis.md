---
id: DAS-1449
title: Fanout-tickets + deferred synthesis gating (P5)
status: done
assignee: backend-em
author: ceo
dept: engineering
priority: p1
parent: DAS-1440
goal: organism-ws1-pulse
depends_on: [DAS-1442]
zone: daslab-cycle
created: 2026-07-03
updated: 2026-07-03
---

## Description

**What & why.** DasLab's planner today emits a static set of board tickets up
front. The ORGANISM program (workstream WS1 — "pulse") needs a *dynamic
fanout* primitive: a single parent ticket can, at dispatch time, expand into
**N runtime-generated child tickets** — each carrying a **private per-child
payload** — plus **one synthesis ticket** that aggregates the children's
results. The synthesis ticket must NOT run until every one of its sibling
children has closed. This is the map/reduce shape (`fan-out` → `join`) missing
from the current one-shot planner, and it is the enabling primitive for the
pulse loop's variable-width work.

**AADL stage.** GATE-3 Development. This is buildable engine work behind the
GATE-2 (Design) close carried by the parent epic DAS-1440; do not re-open
design here — implement to the design of record.

**Extend-vs-new posture — EXTEND, do not rebuild.** The gating machinery
already exists: `/daslab-cycle`'s selection step already treats a ticket whose
`depends_on:` names a not-yet-`done` id as **not actionable** and skips it,
counting it `dep-blocked` (see
`.claude/skills/daslab-cycle/SKILL.md` step 3). The deferred-synthesis refusal
MUST be built on this existing `depends_on` gating semantics rather than a new
parallel mechanism. The synthesis ticket simply declares `depends_on:` = the
list of its N runtime child ids; the dispatcher's existing dep-blocked skip
then refuses to launch it until all siblings are `done`. The only genuinely
new surface is (a) the planner-side *fanout emission* (materialising N children
+ 1 `defer: true` synthesis ticket at runtime with private payloads) and
(b) recognising the `defer: true` marker so a deferred ticket is never launched
early even if a race would otherwise make it look actionable.

**Key existing files this touches (paths, repo root):**

- `.claude/skills/daslab-cycle/SKILL.md` — the orchestrator spec. Step 3
  (Select every actionable ticket) is where the `depends_on` → `dep-blocked`
  skip lives and where the deferred-ticket refusal must be documented/extended.
  Step 5 (Dispatch) is where fanout children are materialised into worktrees.
- `scripts/check_dependency_graph.py` — validates `depends_on:` / `zone:`
  frontmatter: no dangling deps, acyclic graph, well-formed zone. Runtime
  fanout children MUST satisfy this validator (every synthesis `depends_on`
  id must resolve to a real child ticket on the board; no cycle). Extend or
  reuse its `_load` / `scan` helpers for the fanout invariant checks; do not
  fork a second frontmatter parser.
- `board/tickets/*.md` — the ticket frontmatter schema the children and the
  synthesis ticket are written into (`depends_on`, `zone`, `status`, plus the
  new `defer:` flag and a private-payload carrier).
- `board/README.md` — board schema; document the `defer:` field and the
  private-payload convention here if the schema is centrally described.

**Private per-child payloads.** Each runtime child gets its own payload
(the slice of work it owns) that is NOT shared with its siblings — carried in
the child ticket body / a dedicated frontmatter or body block, scoped to that
child only. The synthesis ticket receives the *join* (references to the closed
children), never the raw private payloads of siblings unless a child result
was explicitly published.

**Constraint — org-engine work.** This is DasLab-platform (org-engine) work:
the frontmatter carries NO `project:` field (board_lint R9). The fanout
primitive lives in the engine (`.claude/skills/daslab-cycle/` + `scripts/`),
never in a project folder.

## Acceptance criteria

- [ ] Fanout emission: the planner/dispatcher can, at runtime, emit **N child
      tickets + exactly 1 synthesis ticket** from a single fanout parent, with
      N determined at dispatch time (not hard-coded).
- [ ] The synthesis ticket is marked `defer: true` and declares
      `depends_on:` = the list of all N runtime child ids.
- [ ] Private per-child payloads are supported: each child ticket carries its
      own payload block, isolated from its siblings (no sibling can read
      another child's private payload).
- [ ] Dispatcher refusal: the dispatcher REFUSES to launch the deferred
      synthesis ticket while ANY sibling child is not `done` — reusing the
      existing `depends_on` → `dep-blocked` skip semantics (SKILL.md step 3),
      not a new parallel gate.
- [ ] A `defer: true` ticket is never launched early even if a race would make
      it momentarily look actionable (the defer marker is a hard guard).
- [ ] Once ALL N children are `done`, the synthesis ticket becomes actionable
      in the next wave and is dispatched normally.
- [ ] Test: an automated test proves the dispatcher skips the deferred
      synthesis ticket while a sibling is open, and dispatches it once all
      siblings are `done` (dep-blocked → actionable transition).
- [ ] Runtime fanout children pass `scripts/check_dependency_graph.py`:
      the synthesis `depends_on` ids all resolve to real child tickets, no
      dangling deps, acyclic graph, `zone:` well-formed.
- [ ] The `defer:` field and the private-payload convention are documented in
      the board schema (`board/README.md`) and in `.claude/skills/daslab-cycle/SKILL.md`.
- [ ] Frontmatter carries NO `project:` field; `scripts/board_lint.py` (R9)
      passes for the touched engine tickets.

## Log

### 2026-07-03 — CEO
Created from ORGANISM program-plan decomposition (/daslab-plan). Spec-of-record: docs/research/ORGANISM-PROGRAM-PLAN.md.

### 2026-07-03 — Backend Engineer 2
Implemented P5 fanout-tickets + deferred-synthesis gating. All acceptance criteria met.

**What was built:**
- `scripts/fanout.py` — `emit_fanout()` materialises N child tickets + 1 synthesis ticket at runtime.  Each child carries a private `## Fanout Payload` section (isolated per file).  The synthesis ticket is written with `defer: true` and `depends_on: [child1, ..., childN]`.  `is_actionable()` implements the dispatcher gating logic (dep-blocked skip + defer hard guard) as a reusable helper.
- `scripts/check_dependency_graph.py` — extended `_load()` to also parse the `defer:` field; added a new `scan()` rule that rejects `defer: true` tickets with empty `depends_on` (would never become actionable).
- `.claude/skills/daslab-cycle/SKILL.md` — Step 3: added the Fanout deferred-synthesis guard paragraph (defer: true hard guard on top of dep-blocked skip).  Step 5: added sub-item 5e documenting fanout emission (N children + 1 deferred synthesis, validation, dispatch rules, payload-isolation contract).  Bumped `CACHE_PREFIX_VERSION` from `v10-adr-renumber` to `v11-fanout-deferred` and ran `check_cache_prefix.py --fix` (baseline regenerated).
- `board/README.md` — added `defer:` row to the optional governance fields table; added `## Fanout Payload` body-convention section documenting the private-payload isolation contract.
- `tests/test_fanout_deferred.py` — 23 tests: emission shape, payload isolation, runtime N, dispatcher gating (dep-blocked while child open, actionable once all done), defer hard guard, check_dependency_graph validation, SKILL.md token guards.

**Validators:** diagnostics 100/100, board_lint 0, check_cache_prefix exit 0, check_dependency_graph clean, 746 pytest passed / 1 skipped.

### 2026-07-03 — Orchestrator (/daslab-cycle collect)
Done via local-only done-gate: green diagnostics(100/100)/board_lint/pytest(810) + combined-merge verification (pure-code review collapsed into orchestrator+validator verification per local-only strategy). fanout.py + check_dependency_graph defer-guard + SKILL.md (CACHE_PREFIX v11). check_cache_prefix OK; merged to local main.
