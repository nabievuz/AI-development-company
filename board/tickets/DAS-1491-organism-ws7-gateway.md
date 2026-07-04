---
id: DAS-1491
title: ORGANISM WS7 — GATEWAY (Project-OS compiler)
status: done
assignee: cpo
author: ceo
dept: engineering
priority: p1
parent: 
goal: organism-ws7-gateway
created: 2026-07-03
updated: 2026-07-03
---

## Description

**EPIC — Project-OS compiler.** This work-stream kills gap **G9** by giving DasLab a
*gateway compiler* that turns a declarative **Project-OS pack** into a coherent tree of
stage-gated story tickets, without ever relaxing org law.

**Why.** Today a new project is decomposed by hand each time: the constitution, the layer
map, and the story files are re-derived per goal, so consistency and generality depend on
whoever runs `/daslab-plan`. WS7 makes that a compile step — one pack in, a verified
ticket tree out — so any well-formed Project-OS pack produces the same high-quality,
law-abiding decomposition every time.

**Pattern P22** (spec-of-record): *Spec-Kit constitution × Agent-OS layers × BMAD story
files*, fused with **AADL** (the DasLab AI-Agent Development Lifecycle 6-gate model). The
three source patterns each contribute one layer:
- **Constitution (Spec-Kit):** the non-negotiable rules the compiler must honor = the
  **QONUN laws** (Project Placement, AI-Agent Lifecycle, Founder-Approved Goal Queue,
  Model Allocation, Persistent Memory) **plus** project-local constraints. Project-local
  constraints may *tighten* but NEVER relax org law.
- **Layers (Agent-OS):** the standard project surface (mission / roadmap / stack /
  decisions) the pack declares and the compiler reads.
- **Story files (BMAD):** the compiled output unit — self-contained, embedded-context
  story tickets that a role subagent can execute end to end.

**Compiler capability delivered by this epic:**
1. **Pack format** — a declarative Project-OS pack schema (constitution refs, layer
   map, story templates, gate map).
2. **`gateway_compile`** — the compile entrypoint: pack → validated story-ticket tree.
3. **Stage-gated delivery** — every compiled ticket carries its AADL stage/gate so
   `/daslab-cycle` will not dispatch a ticket behind an open gate.
4. **Import-ban** — a fail-closed check that rejects any pack whose local constraints
   would relax org law or whose story tickets would leak outside the Project Placement
   Law.

**Extend-vs-new.** EXTEND the existing planning machinery — do not fork it.
`/daslab-plan` (`.claude/skills/daslab-plan/SKILL.md`) already decomposes goals and
already enforces the Founder discovery gate via `scripts/check_approved_goal_queue.py`;
WS7 adds the pack-driven *compile* front-end to that same pipeline and reuses the AADL
gate model from `governance/policies/ai-agent-lifecycle.md`. New surface is limited to the
pack format + `gateway_compile` + the import-ban validator.

**Demonstration (this epic must show it works).** Author one **sample Project-OS pack** and
compile it to **>= 25 coherent story tickets**, then run a **generality check** on a
**second pack** to prove the compiler is not overfit to the first. The full 0→100 delivery
of a real project through all 6 AADL gates is documented as the *scaled operation the
gateway enables* — i.e. the epic proves the compiler capability and describes the scaled
run, it does not itself have to ship a whole product.

**Children:** DAS-1492 .. DAS-1496.

**Spec-of-record:** `docs/research/ORGANISM-PROGRAM-PLAN.md` §4 (WS7).

**Key files + paths:**
- `docs/research/ORGANISM-PROGRAM-PLAN.md` — program plan, §4 WS7 (authoritative scope).
- `governance/policies/ai-agent-lifecycle.md` — AADL 6-gate model the gate map binds to.
- `.claude/skills/daslab-plan/SKILL.md` — the planning pipeline WS7 extends.
- `scripts/check_approved_goal_queue.py` — Founder discovery/approval gate to reuse.
- `CLAUDE.md` — QONUN laws that form the immutable constitution the compiler honors.

## Acceptance criteria

- [ ] AADL 6-gate closure for the WS7 epic (all of Planning → Design → Development →
      Testing → Deployment → Maintenance gates closed and logged in the stage-board).
- [ ] **Pack format** defined: a declarative Project-OS pack schema (constitution refs +
      layer map + story templates + gate map) with a documented, validated example.
- [ ] **`gateway_compile`** implemented: pack in → validated story-ticket tree out, each
      ticket carrying its AADL stage/gate.
- [ ] **Stage-gated delivery** honored: compiled tickets behind an open gate are not
      dispatchable by `/daslab-cycle`.
- [ ] **Import-ban / broken pack rejected**: a malformed pack, or one whose project-local
      constraints would relax org law, is rejected fail-closed (with a clear reason).
- [ ] **Discovery gate blocks**: an unapproved goal is blocked by
      `check_approved_goal_queue.py` before any tickets are compiled.
- [ ] **Compile demonstration**: the sample Project-OS pack compiles to **>= 25 coherent
      story tickets**, and a **second pack** passes the generality check.
- [ ] Constitution invariant proven: project-local constraints may tighten but never
      relax QONUN org law; Project Placement Law is never leaked by compiled tickets.
- [ ] Children DAS-1492..1496 exist and are traceable to this epic.

## Log

### 2026-07-03 — CEO
Created from ORGANISM WS7 GATEWAY decomposition (/daslab-plan). Spec-of-record: docs/research/ORGANISM-PROGRAM-PLAN.md.
READ: docs/research/ORGANISM-PROGRAM-PLAN.md, governance/policies/ai-agent-lifecycle.md, .claude/skills/daslab-plan/SKILL.md, scripts/check_approved_goal_queue.py.
EPIC. Project-OS compiler — kills gap G9. Pattern P22 (Spec-Kit constitution × Agent-OS layers × BMAD story files, fused with AADL). Spec-of-record: ORGANISM-PROGRAM-PLAN.md §4 WS7. Children DAS-1492..1496. Constitution = the QONUN laws + project-local constraints (never relaxing org law). This epic delivers the full compiler capability (pack format + gateway_compile + stage-gated delivery + import-ban) and DEMONSTRATES a sample Project-OS pack compiling to >=25 coherent story tickets + a generality check on a second pack; the full 0→100 delivery through all 6 gates is documented as the scaled operation the gateway enables. Acceptance = AADL 6-gate closure + a broken pack rejected + discovery gate blocks + compile demonstration.
Constraints: org-engine ticket (this WS7 machinery), NO project: field.

### 2026-07-03 — Orchestrator (/daslab-run)
Done. EPIC CLOSED — WS7 GATEWAY complete. ADR-0030 + PROJECT-OS-PACK spec; gateway_compile (validate/discovery-gate/research/approved-check/compile); stage-gated delivery w/ GATE-5 machine-enforced; E2E 2 packs compile >=25 tickets each w/ generality; donor import-ban validator. Children DAS-1492..1496 done.
