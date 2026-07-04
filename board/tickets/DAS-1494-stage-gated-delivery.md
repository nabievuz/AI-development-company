---
id: DAS-1494
title: Stage-gated delivery with GATE-5 machine enforcement
status: done
assignee: security-lead
author: ceo
dept: engineering
priority: p1
parent: DAS-1491
goal: organism-ws7-gateway
depends_on: [DAS-1493]
zone: stage-gated
created: 2026-07-03
updated: 2026-07-04
---

## Description

**What/why.** DasLab already mandates the six-stage AI-agent lifecycle
(`Planning → Design → Development → Testing → Deployment → Maintenance`) via
[`governance/policies/ai-agent-lifecycle.md`](../../governance/policies/ai-agent-lifecycle.md),
and there is an existing never-auto-approve law for the deployment gate
(`gate5_deployment`). What is missing is **machine enforcement end-to-end**: today
the gate order is a documented convention that `/daslab-cycle` and the board tooling
do not hard-block on. This ticket wires **stage-gated delivery** so that a project
board is actually *executed through the AADL gates*, gates emit interrupt-cards, and
a **GATE-5-open state provably blocks any production deploy** — enforced by a
validator/rule, not by convention. This is GATE-3 (P22) of the ORGANISM WS7 GATEWAY.

**Embedded context.** This is an org-engine (DasLab-platform) ticket — it builds the
WS7 gateway machinery itself (validators, rules, docs), NOT any project's product.
Per the Project Placement Law this carries **no `project:` field** and lives on the
org board. The `gateway_compile.py` script (WS7) is the compilation entry point that
this stage-gating plugs into; interrupt-cards follow the DAS-1446 pattern under
`board/interrupts/`. The Maintenance stage must schedule recurring health/eval runs
that tie into WS4 (heartbeat) and WS6 (evals).

**Extend-vs-new.** EXTEND existing machinery, do not fork it:
- Extend the gate/lifecycle model in `governance/policies/ai-agent-lifecycle.md`
  (add the machine-enforcement clause referencing this rule).
- Extend `scripts/gateway_compile.py` (WS7 compile) to walk the AADL gate order and
  refuse to advance a board past an open gate.
- Extend `scripts/board_lint.py` with a validator rule: a Stage-5 (Deployment)
  ticket must be blocked while GATE-4 (Testing) is open, and any production-deploy
  ticket must be blocked while GATE-5 is open. Reuse the existing `gate5_deployment`
  never-auto-approve check rather than adding a parallel path.
- Emit gate events as interrupt-cards using the existing `board/interrupts/`
  DAS-1446 format; do NOT invent a new card schema.
- Reference `config/risk_taxonomy.yaml` for the deploy-risk classification the
  GATE-5 block keys off.
- The `/daslab-cycle` skill (`.claude/skills/daslab-cycle/SKILL.md`) must consult
  these gates when triaging so it does not dispatch tickets sitting behind an open
  gate.

**Key files + paths.**
- `scripts/gateway_compile.py` — WS7 compile; add AADL gate-walk.
- `scripts/board_lint.py` — add stage-gate validator rules + tests hook.
- `governance/policies/ai-agent-lifecycle.md` — machine-enforcement clause.
- `.claude/skills/daslab-cycle/SKILL.md` — gate-aware triage note.
- `config/risk_taxonomy.yaml` — deploy-risk source for GATE-5 keying.
- `board/interrupts/` — gate interrupt-cards (DAS-1446 format).

**Do NOT deploy anything.** Implement as validators/rules + doc only.

## Acceptance criteria

- [ ] A project board runs through the AADL gates (Planning → Design → Development
      → Testing → Deployment → Maintenance) under `gateway_compile.py` / triage.
- [ ] Gates emit interrupt-cards to `board/interrupts/` in the DAS-1446 format.
- [ ] GATE-5 open ⇒ NO production deploy — machine-enforced end-to-end via the
      existing `gate5_deployment` never-auto-approve law, with an explicit check
      added/validated (not convention).
- [ ] The Maintenance stage schedules recurring health/eval runs (WS4 heartbeat +
      WS6 evals).
- [ ] Test: a Stage-5 (Deployment) ticket is blocked while GATE-4 (Testing) is open.
- [ ] Test: a GATE-5-open state blocks a production-deploy ticket.
- [ ] `/daslab-cycle` does not dispatch tickets sitting behind an open gate.
- [ ] Full test suite: 0 failed; diagnostics 100/100.
- [ ] Org-engine ticket — NO `project:` field (board_lint R9 passes).

## Log

### 2026-07-03 — CEO
Created from ORGANISM WS7 GATEWAY decomposition (/daslab-plan). Spec-of-record: docs/research/ORGANISM-PROGRAM-PLAN.md.
READ: scripts/gateway_compile.py, governance/policies/ai-agent-lifecycle.md, .claude/skills/daslab-cycle/SKILL.md, scripts/board_lint.py, config/risk_taxonomy.yaml.
Scope+acceptance (expand; keep frontmatter exact): GATE-3 (P22). Wire stage-gated delivery so /daslab-cycle executes a project board through the AADL gates; gates emit interrupt-cards (board/interrupts/, DAS-1446); GATE-5 open => NO production deploy (existing gate5_deployment never-auto-approve law, now machine-enforced end-to-end — add/validate the check). Maintenance stage schedules recurring health/eval runs (WS4 heartbeat + WS6 evals). Implement as validators/rules + doc (do NOT deploy anything). Tests: a Stage-5 deploy ticket is blocked while GATE-4 open; GATE-5-open blocks prod deploy.
Acceptance: [ ] project board runs through AADL gates; [ ] gates emit interrupt-cards; [ ] GATE-5 open => no prod deploy (machine-enforced, tested); [ ] maintenance schedules recurring runs; [ ] full suite 0 failed, diagnostics 100/100.
Constraints: org-engine ticket (this WS7 machinery), NO project: field.

### 2026-07-04 — CTO
Implemented P22 stage-gated delivery, machine-enforced end-to-end (validators/rules + doc; deployed nothing).

New single-source-of-truth module `scripts/stage_gate.py` (gate decision keyed on the `stage: GATE-N` frontmatter `gateway_compile.py` stamps + `goal`; reuses `check_gates` loader/parser and `check_never_auto_approve` matcher — no parallel path):
- `gate_status` / `gate_order_violations`: a stage-N ticket may not ADVANCE (`in_progress`/`in_review`/`done`) while GATE-(N-1) is open. A `todo`/`backlog` stage ticket is the legitimate waiting state (never flagged) — that is why a freshly compiled all-todo board stays clean.
- `production_deploy_violations`: GATE-5 => no prod deploy — reuses the `gate5_deployment` category from `config/risk_taxonomy.yaml` (a) auto-approved deploy blocked (never-auto-approve, QONUN-5) and (b) a deploy ACTION advanced while its goal's GATE-5 is open blocked (the Stage-5 gate ticket itself is excluded — its completion closes GATE-5).
- `walk_gates` + `emit_gate_cards`: walks a compiled board and refuses to advance past an open gate; open blocking gates surface as DAS-1446-schema interrupt-cards (idempotent; Founder sign-off, machine never auto-answers). `maintenance_schedule`: WS4 heartbeat tick + WS6 golden-eval + ArcRift hygiene as DATA (no OS-scheduler install, ADR-0027 SI-1).

Wiring: `board_lint.py` R12 (additive; fail-open on import/config; lazy import breaks the cycle) — real org board stays 0. `gateway_compile.py` `--gate-walk [--emit-cards]` mode. `SKILL.md` step-3 AADL-gate note augmented + CACHE_PREFIX_VERSION bumped v16→v17 + baseline re-`--fix`ed. Doc: `ai-agent-lifecycle.md` §5.1 machine-enforcement clause + §3 Stage-6 maintenance scheduling.

Tests: `tests/test_stage_gate.py` (24) — Test A (Stage-5 blocked while GATE-4 open; todo-not-flagged; clears when GATE-4 done), Test B (GATE-5-open blocks a prod-deploy action; auto-approved gate5 blocked), board_lint R12 wiring, walk/cards schema+idempotency, maintenance schedule, freshly-compiled-board regression, CLI + gateway `--gate-walk` smoke.

VERIFY (FULL, all green): pytest 1600 passed / 1 skipped; diagnostics 100/100; board_lint 0 (56 tickets); check_links / check_precedence / check_never_auto_approve / check_gates / check_project_isolation / check_no_dead_runtime OK; ruff clean; check_cache_prefix OK (v17). LOCAL-ONLY commit; no push. Reviewer: security-lead (CTO's ROUTING reviewer is CEO = the author, so escalated per ROUTING; GATE-5/never-auto-approve is the Stage-5 Consulted security surface). → in_review.

### 2026-07-03 — Orchestrator (/daslab-cycle collect)
Done. stage_gate.py (AADL gate enforcement: gate_order_violations, GATE-5 production_deploy_violations machine-enforced via reused gate5_deployment, emit_gate_cards, maintenance_schedule) + board_lint R12 + gateway_compile --gate-walk + SKILL v17; 24 tests (Stage-5 blocked while GATE-4 open; GATE-5-open blocks prod deploy).
