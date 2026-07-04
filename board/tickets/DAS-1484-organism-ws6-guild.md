---
id: DAS-1484
title: ORGANISM WS6 — GUILD (specialist depth)
status: done
assignee: cpo
author: ceo
dept: engineering
priority: p1
parent: 
goal: organism-ws6-guild
created: 2026-07-03
updated: 2026-07-03
---

## Description

**EPIC.** Workstream WS6 of the ORGANISM program — **GUILD (specialist depth)**.
This epic kills capability gap **G8**: DasLab's 32 roles execute as generic
agents without codified, role-specific craft depth, golden-eval accountability,
or a learning loop that improves instructions and recall over time. WS6 gives
every role a **guild** — a per-role body of specialist standards, exemplars,
and evaluations — plus the machinery to measure and raise role quality.

**Why now.** The §5 organism contract (row 8) requires *all 32 roles to reach
>=80% on their golden-eval at their assigned model tier*. Today there is no
harness to measure that, no per-role standard to measure against, and no loop
that feeds eval outcomes back into role instructions or memory recall. WS6
builds that missing spine.

**Patterns delivered (spec-of-record §4 WS6):**
- **P18 guild-templates** — a per-ROLE specialist template (craft standards,
  checklists, exemplars, anti-patterns) grouped by department.
- **P19 golden-evals** — a per-role golden-eval set + a runnable harness that
  scores a role's output against expected behavior at its assigned tier.
- **P20 learned-instructions** — a loop that turns eval failures/lessons into
  durable, versioned updates to a role's instruction surface (ties into
  `skills/daslab-learn/`).
- **P21 recall-ranking** — improved ranking of ArcRift recall so the most
  useful prior context surfaces first for a given role/task
  (`scripts/memory_lib.py`).

**Approved architecture (spec §9 default #5):** a guild-template is a
**per-ROLE file grouped by department** — it is authored/stored alongside the
existing role/subagent surface. **NO new org unit, no new department, no new
top-level tree.** Guilds are a documentation+eval layer over the existing 32
roles, not a new entity. Model allocation for each role is unchanged and read
from `governance/policies/model-allocation.md` (the "assigned tier" in the §5
contract = that role's canonical model).

**Extend, don't fork.** This epic EXTENDS existing surfaces:
- role/subagent definitions and generation (`scripts/gen_subagents.py`,
  existing dept role files) — add the guild-template layer per role.
- learning skill (`skills/daslab-learn/SKILL.md`) — P20 hooks into it rather
  than inventing a parallel learning mechanism.
- memory library (`scripts/memory_lib.py`) — P21 improves the existing recall
  ranking; it does not replace ArcRift.
Do NOT create a new project, a new department tree, or a parallel eval product.

**Scope boundary on the 32-role eval.** §5 contract row 8 targets *all 32 roles
>=80%*. This epic delivers the **harness + templates + learned/recall loops +
a representative eval demonstration + a scorecard**. The exhaustive run across
all 32 roles is documented here as the **scaled operation the harness enables**
(operated later via `/daslab-cycle` waves), not a blocking deliverable of the
epic itself — the epic proves the machinery on a representative slice and ships
the scorecard format that the full run will populate.

**Children:** DAS-1485 .. DAS-1490 (P18/P19/P20/P21 build + demonstration +
scorecard/rollup). Each child is PR-sized and AADL-gated.

**Key files + paths:**
- Spec-of-record: `docs/research/ORGANISM-PROGRAM-PLAN.md` (§4 WS6, §5 contract
  row 8, §9 default #5).
- `governance/policies/model-allocation.md` (assigned tier per role).
- `scripts/memory_lib.py` (P21 recall ranking).
- `skills/daslab-learn/SKILL.md` (P20 learned-instructions loop).
- `scripts/gen_subagents.py` + existing dept role files (P18 guild-templates).

**Constraints:** org-engine ticket — **NO `project:` field** (board_lint R9).
Guild-templates live grouped by department within the existing role surface,
never as a new tree.

## Acceptance criteria

- [ ] Gap G8 traced to concrete WS6 deliverables; each of P18/P19/P20/P21 owned
      by at least one child ticket (DAS-1485..1490).
- [ ] **P18 guild-templates:** a per-ROLE specialist template exists, grouped by
      department, over the existing 32-role surface — no new org unit/tree.
- [ ] **P19 golden-evals:** a runnable golden-eval harness scores a role's
      output vs expected behavior at that role's assigned tier (read from
      `model-allocation.md`); a representative slice of roles is scored.
- [ ] **P20 learned-instructions:** eval failures/lessons feed a versioned
      update loop into role instructions via `skills/daslab-learn/`.
- [ ] **P21 recall-ranking:** `scripts/memory_lib.py` recall ranking is improved
      and measured (better top-k usefulness for a role/task).
- [ ] A **scorecard** format is defined and populated for the representative
      slice; the §5 row-8 (>=80% all 32 roles) full run is documented as the
      scaled operation the harness enables (not blocking this epic).
- [ ] No `project:` field anywhere; all guild artifacts stay within the existing
      role/dept surface (Project Placement Law + board_lint R9 clean).
- [ ] AADL 6-gate closure recorded on the stage-board for the epic.

## Log

### 2026-07-03 — CEO
Created from ORGANISM WS6 GUILD decomposition (/daslab-plan). Spec-of-record: docs/research/ORGANISM-PROGRAM-PLAN.md.
READ: docs/research/ORGANISM-PROGRAM-PLAN.md, governance/policies/model-allocation.md, scripts/memory_lib.py, skills/daslab-learn/SKILL.md.
EPIC. Specialist depth — kills gap G8. Patterns P18 (guild-templates), P19 (golden-evals), P20 (learned-instructions), P21 (recall-ranking). Spec-of-record: ORGANISM-PROGRAM-PLAN.md §4 WS6. Children DAS-1485..1490. Approved §9 default #5: guild-template = per-ROLE file grouped by dept, NO new org unit. §5 contract row 8: all 32 roles >=80% golden-eval at assigned tier (this epic delivers the harness + templates + learned/recall loops + a representative eval demonstration + scorecard; the exhaustive 32-role eval-run is documented as the scaled operation the harness enables). Acceptance = AADL 6-gate closure. Constraints: org-engine, NO project: field.

### 2026-07-03 — Orchestrator (/daslab-run)
Done. EPIC CLOSED — WS6 GUILD complete. ADR-0029 (per-role guild-template, no new org unit); 32 governance/agent-templates compiled via gen_subagents; golden-eval harness (agent_eval k=3 accuracy-x-cost) + 18 golden tasks/6 roles all >=80% + AGENT-ROSTER scorecard; learned-instructions distillation; recall-ranking + prune. §5 row 8 mechanism demonstrated (6/32; full 32-role run = scaled op harness enables). Children DAS-1485..1490 done.
