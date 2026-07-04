---
id: DAS-1486
title: Generate guild-templates for all 32 roles and compile
status: done
assignee: chairman
author: ceo
dept: engineering
priority: p1
parent: DAS-1484
goal: organism-ws6-guild
depends_on: [DAS-1485]
zone: agent-templates
created: 2026-07-03
updated: 2026-07-03
---

## Description

**What.** Establish a single canonical source-of-truth per agent role: a
`governance/agent-templates/<role>.md` file for ALL 32 roles, then wire the
subagent generator to compile agents FROM those templates. This is the GATE-3
(P18) deliverable of ORGANISM WS6 GUILD, per ADR-0029.

**Why.** Today each role's behavior is scattered across the `<dept>/agents/<role>/AGENTS.md`
overlays, `governance/policies/model-allocation.md` (model + effort tier), and
`governance/communication-flows.yaml` (which routes a role may take). There is
no one place that composes a role's full "guild template." The organism program
needs a stable, drift-safe per-role template that: (a) carries the role's model
and effort verbatim, (b) records its allowed communication routes, and (c) holds
an empty `## Learned` section that a later ticket (DAS-1489) fills with
distilled lessons. Compiling agents from templates makes the generator the one
throat to choke and keeps `check_agents_sync` meaningful.

**Extend, do not rewrite.** Prefer a GENERATOR that seeds each template from the
already-existing overlays + policy + flows over hand-authoring 32 files — 32
hand-written files drift immediately and are inconsistent. Extend the existing
`scripts/gen_subagents.py` so it READS `governance/agent-templates/<role>.md`
during compilation (rather than assembling directly from the scattered sources).
Keep `scripts/check_agents_sync.py` green via the regenerate-and-diff invariant.

**Embedded context / key files + paths.**
- Spec-of-record: `docs/research/ORGANISM-PROGRAM-PLAN.md` (WS6 GUILD, P18, ADR-0029).
- `scripts/gen_subagents.py` — subagent compiler; wire it to read templates.
- `scripts/check_agents_sync.py` — the sync/diff gate that must stay green.
- `governance/policies/model-allocation.md` — model + effort per role (opus ×10,
  sonnet ×19, haiku ×3; Tier F decommissioned — no Fable).
- `governance/communication-flows.yaml` — allowed routes per role.
- `<dept>/agents/<role>/AGENTS.md` — existing per-role overlays to seed from.
- New tree: `governance/agent-templates/<role>.md` (32 files, one per role).

## Acceptance criteria

- [x] `governance/agent-templates/<role>.md` exists for all 32 roles.
- [x] Each template seeded from the existing `<dept>/agents/<role>/AGENTS.md`
      overlay + `model-allocation.md` + `communication-flows.yaml`.
- [x] Model + effort carried VERBATIM (opus ×10, sonnet ×19, haiku ×3; NO Tier F).
- [x] Each template's allowed communication routes match `communication-flows.yaml`.
- [x] Each template carries an empty `## Learned` section (reserved for DAS-1489).
- [x] A generator (seed-from-existing) produces the templates — not 32 hand-authored files.
- [x] `scripts/gen_subagents.py` compiles agents FROM the templates (extended, not replaced).
- [x] `scripts/check_agents_sync.py` is green (regenerate-and-diff clean).
- [x] Tests added for template generation + compile path.
- [x] Full suite: 0 failed; diagnostics 100/100.

**Constraints:** org-engine ticket — NO `project:` field in frontmatter.

## Log

### 2026-07-03 — CEO
Created from ORGANISM WS6 GUILD decomposition (/daslab-plan). Spec-of-record: docs/research/ORGANISM-PROGRAM-PLAN.md.
READ: scripts/gen_subagents.py, governance/policies/model-allocation.md, governance/communication-flows.yaml, engineering/agents, scripts/check_agents_sync.py.
Scope+acceptance (expand; keep frontmatter exact): GATE-3 (P18). Build governance/agent-templates/<role>.md for ALL 32 roles per ADR-0029 — seed from the existing <dept>/agents/<role>/AGENTS.md overlays + model-allocation.md (model+effort verbatim) + communication-flows.yaml (allowed routes). Prefer a GENERATOR (seed-from-existing) over 32 hand-authored files to stay consistent + drift-safe. Wire gen_subagents.py to read the templates (extend, keep check_agents_sync green — regenerate-and-diff). Each template carries an empty ## Learned section (for DAS-1489). Tests.
Acceptance: [ ] governance/agent-templates/<role>.md for all 32 roles; [ ] model+effort verbatim (opus x10/sonnet x19/haiku x3, no Tier F); [ ] gen_subagents compiles templates; [ ] check_agents_sync green; [ ] full suite 0 failed, diagnostics 100/100.

### 2026-07-03 — CPO
GATE-3 (P18) delivered per ADR-0029 G-1..G-5. LOCAL-ONLY branch (strict no-push).

**Built.**
- `scripts/gen_agent_templates.py` (NEW) — seed-from-existing generator: composes
  `governance/agent-templates/<role>.md` for all 32 roles from the `<dept>/agents/<role>/AGENTS.md`
  overlay (identity/goal/priors) + `model-allocation.md` (model+effort VERBATIM) +
  `communication-flows.yaml` (outbound routes). Closed craft field set (G-2): identity,
  goal, behavioral priors, toolkit allowlist (per-dept), produces/consumes defaults,
  allowed routes, eval-baseline ref (`evals/<role>/`), empty `## Learned` sink. Idempotent
  (delete-all + rewrite; byte-stable).
- `scripts/gen_subagents.py` (EXTENDED, not replaced) — main() now lazy-imports
  gen_agent_templates, regenerates the templates, reads model+effort BACK from each
  template (compile FROM template, G-4), cross-checks vs `load_alloc()` and fails loudly on
  drift (G-3), and emits a `> Guild template (ADR-0029)` reference line into every shim.
  Added `load_template_alloc()` + template-frontmatter regexes; sparse-worktree tolerant
  (falls back to direct sources when templates absent).
- `tests/test_gen_agent_templates.py` (NEW, 15 tests) — 32-template coverage, verbatim
  model/effort (10/19/3, no Tier F, haiku omits effort), routes==flows, empty `## Learned`,
  shim-references-template, shim-model==template-model, idempotency, load_template_alloc unit.
- 32 templates + 32 regenerated shims + ROUTING.md committed in sync.

**VERIFY (FULL, green).** `pytest` 1509 passed / 1 skipped (0 failed); `diagnostics.py`
100/100; `board_lint.py` 0 violations (50 tickets); `check_agents_sync.py` OK — 32 shims in
sync (policy: 32 rows); `ruff check scripts tests` clean. Regenerate-and-diff clean (two
runs byte-identical).

**Routing.** status → in_review; assignee → chairman. Reviewer rule: cpo's manager is CEO,
but CEO authored this ticket, so escalate one level to chairman (same as DAS-1485). No
SSOT edited in place (model-allocation / communication-flows / schema untouched); no new
org node/edge; org-engine ticket, no `project:` field. No escalation needed.

### 2026-07-03 — Orchestrator (/daslab-cycle collect)
Done via local-only done-gate: full suite 1534 + diagnostics 100/100 + check_agents_sync green (combined-merge verified; cleared WS3-proof residue from board/.events.jsonl). gen_agent_templates.py generator -> 32 governance/agent-templates/<role>.md (model+effort verbatim, routes from flows, empty ## Learned); gen_subagents compiles FROM templates + drift-checks; 32 shims byte-stable, check_agents_sync green; 15 tests.
