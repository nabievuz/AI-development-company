---
id: DAS-1485
title: Author ADR-0029 guild model and agent-template compilation
status: done
assignee: chairman
author: ceo
dept: engineering
priority: p1
parent: DAS-1484
goal: organism-ws6-guild
zone: docs/adr
created: 2026-07-03
updated: 2026-07-03
reviewed: 2026-07-03
---

## Description

GATE-1 Planning ticket from the ORGANISM WS6 GUILD decomposition. The goal is to
formalize, via an Architecture Decision Record, how DasLab captures reusable
per-role "guild" knowledge as compilable **agent-templates** — without inventing
a new org unit.

**What.** Author `docs/adr/0029-guild-model.md` deciding (per spec §9 default #5)
that a *guild-template* is a per-ROLE file at
`governance/agent-templates/<role>.md`, grouped by department. Each template
carries:

- identity / goal / behavioral-priors for the role,
- a toolkit allowlist,
- `model` + `effort` copied **VERBATIM** from
  `governance/policies/model-allocation.md` (no Tier F — Fable 5 is
  decommissioned),
- `produces` / `consumes` defaults,
- the allowed `communication-flows` routes for the role,
- an eval-baseline reference,
- a `## Learned` section for accumulated role knowledge.

**Why.** Role knowledge is currently implicit in the generated subagents and
scattered guidance. A per-role template file makes the "guild" (the shared craft
of a role) an explicit, reviewable, version-controlled artifact — while staying
inside the existing generate-and-diff overlay flow, so no new org unit or
parallel process is introduced.

**Extend vs new.** EXTEND the existing overlay/compile flow — do NOT build a new
pipeline. Templates COMPILE via `scripts/gen_subagents.py` into `.claude/agents/`
(the same overlay the generator already applies). The existing drift guards
(`scripts/check_agents_sync.py` and the org-drift check) keep the generated
`.claude/agents/` in lockstep with the templates via generate-and-diff. The ADR
itself is a NEW file (highest existing ADR is 0028; author 0029) plus a README
index row.

**Key files + paths.**
- Author: `docs/adr/0029-guild-model.md`
- README index + theme: `docs/adr/README.md`
- Model + effort source of truth: `governance/policies/model-allocation.md`
- Compile path: `scripts/gen_subagents.py` → `.claude/agents/`
- Drift guard: `scripts/check_agents_sync.py`
- Comm routes reference: `governance/communication-flows.yaml`
- Templates location decided by ADR: `governance/agent-templates/<role>.md`
- Spec-of-record: `docs/research/ORGANISM-PROGRAM-PLAN.md`

## Acceptance criteria

- [x] ADR-0029 authored + README index row added (GATE-1 sign-off complete)
- [x] Guild-template defined as a per-role file (`governance/agent-templates/<role>.md`), grouped by dept, with NO new org unit
- [x] Compile path specified via `gen_subagents.py` → `.claude/agents/` with the drift guard (`check_agents_sync`; `check_org_drift` named as the sibling org-schema gate) enforcing generate-and-diff
- [x] `model` + `effort` are VERBATIM from `model-allocation.md` (no Tier F / Fable 5)
- [x] diagnostics 100/100

## Log

### 2026-07-03 — CEO
Created from ORGANISM WS6 GUILD decomposition (/daslab-plan). Spec-of-record: docs/research/ORGANISM-PROGRAM-PLAN.md.
READ: docs/adr/README.md, governance/policies/model-allocation.md, scripts/gen_subagents.py, scripts/check_agents_sync.py, governance/communication-flows.yaml.
Scope+acceptance (expand; keep frontmatter exact): GATE-1 Planning. Author docs/adr/0029-guild-model.md deciding (§9 default #5): a guild-template = a per-ROLE file governance/agent-templates/<role>.md (identity/goal/behavioral-priors, toolkit allowlist, model+effort VERBATIM from model-allocation.md, produces/consumes defaults, allowed comm-flows routes, eval baseline ref, a ## Learned section) grouped by dept — NO new org unit. Templates COMPILE via gen_subagents.py -> .claude/agents/ (extends the existing overlay flow; check_agents_sync/check_org_drift guard generate-and-diff). README index row + theme (highest ADR 0028; you author 0029).
Acceptance: [ ] ADR-0029 merged + README row; [ ] guild-template = per-role file, no new org unit; [ ] compile path via gen_subagents + drift guard; [ ] model+effort verbatim (no Tier F); [ ] diagnostics 100/100.
Constraints: org-engine, NO project: field.

### 2026-07-03 — CPO
Authored `docs/adr/0029-guild-model.md` (GATE-1 Planning; CPO decider — GATE-1 is CPO-accountable, RACI §1). Decision resolves §9 Q5 (guild = dept vs craft) by ruling **craft**: a guild is per-ROLE craft captured as `governance/agent-templates/<role>.md`, grouped by dept, **NO new org unit** (no new routing node/edge, no `schema.daslab.yaml` change). Five binding invariants:
- G-1 one template per role key, grouped by dept, zero topology change.
- G-2 closed craft field set: identity/goal/behavioral-priors, toolkit allowlist, model+effort, produces/consumes defaults, allowed comm-flows routes, eval-baseline ref, a `## Learned` sink.
- G-3 model+effort **VERBATIM** from `model-allocation.md` (SSOT), no Tier F / Fable 5 (retired, no restore path), haiku omits `effort`.
- G-4 compiles via existing `gen_subagents.py` → `.claude/agents/` (generate-and-diff clean), guarded by `check_agents_sync.py`. Reconciled the ticket's "check_agents_sync / org-drift" against spec map row 112 ("guarded by check_agents_sync **not** check_org_drift"): `check_agents_sync` is the direct guard; `check_org_drift` is the **sibling** org-schema generate-and-diff gate (R-12/ADR-009), named as pattern precedent only.
- G-5 template references — never re-decides — any SSOT; `## Learned` grows only via `daslab-learn` distillation of Founder-accepted feedback.
Numbering: plan-text calls this "0028"; README ledger already assigned 0028 to cockpit-form-factor, so this takes next free number **0029** (numbering note in the ADR, same reconciliation ADR 0028 used). Added README index row + a WS6 GUILD theme entry. This is a decision doc: NO template file authored, generator untouched — WS6 O6-T02/O6-T03 implement against the contract.
VERIFY (FULL, in worktree): `pytest -q` = 1441 passed / 1 skipped / 0 failed; `diagnostics.py` = 100/100; `board_lint.py` = 0 violations (50 tickets); `ruff check scripts tests` clean.
Committed LOCAL-only (dispatch = STRICT no-push). Set status → in_review, assignee → **chairman** (ticket author is `ceo`; reviewer per ROUTING must not be the author, and ceo is my manager → escalate one level to chairman). Routing note: chairman to review/merge ADR-0029.

### 2026-07-03 — Chairman of the Board
GATE-1 sign-off review of ADR-0029 (guild model). **Verdict: PASS → done.** Reviewed `docs/adr/0029-guild-model.md` + `docs/adr/README.md` against acceptance + GATE-1; not my own work (author = ceo). Verified content:
- **G-1** guild = per-ROLE craft at `governance/agent-templates/<role>.md`, grouped by dept, **NO new org unit** — no `guild:` node, no routing edge, no `schema.daslab.yaml`/`ROUTING.md`/`communication-flows.yaml` topology change; role dept/manager/reporting line unchanged. Resolves §9 Q5 (dept-vs-craft) by ruling *craft*.
- **G-2** closed craft field set (identity/goal/behavioral-priors, toolkit allowlist, model+effort, produces/consumes defaults, allowed comm-flows routes, eval-baseline ref, a `## Learned` sink).
- **G-3** `model`+`effort` **VERBATIM** from `model-allocation.md` (SSOT); valid tiers exactly {opus, sonnet, haiku}; **no Tier F / Fable 5** (retired, no restore path); haiku omits `effort`. Cross-checked against the allocation table (opus×10, sonnet×19, haiku×3 = 32) — faithful.
- **G-4** compiles via existing `gen_subagents.py` → `.claude/agents/` (generate-and-diff clean), guarded by **`check_agents_sync.py` — NOT `check_org_drift`** (correctly reconciled against spec row 112; check_org_drift named only as the sibling org-schema gate). No new validator/generator.
- **G-5** template references — never re-decides — any SSOT; `## Learned` grows only via `daslab-learn` distillation of Founder-accepted feedback.
- **Numbering** correct: 0028 = cockpit-form-factor (occupied), so guild takes next free **0029**; numbering note present. README index row + WS6 GUILD theme entry present; `[0029](0029-guild-model.md)` link resolves.
- **Law check** sound: GATE-1 CPO-accountable (AADL RACI §1); decision doc only (ships no template, no generator change); no never-auto-approve category triggered; no `project:` field (org-engine ticket).
GATES (MAIN checkout): `diagnostics.py` = **100/100**; `board_lint.py` = **0 violations** (50 tickets); `check_agents_sync.py` = **32 shims in sync** (32 policy rows); `pytest -q` = **1494 passed / 1 skipped / 0 failed**.
Checked AC #1 box (GATE-1 sign-off complete). status → **done**; committed LOCAL-only (STRICT no-push). Downstream: WS6 O6-T02 (author templates) / O6-T03 (compile through gen_subagents) build against the G-1…G-5 contract.
