---
id: DAS-1492
title: Author ADR-0030 and PROJECT-OS-PACK spec
status: done
assignee: chairman
author: ceo
dept: engineering
priority: p1
parent: DAS-1491
goal: organism-ws7-gateway
zone: docs/adr-specs
created: 2026-07-03
updated: 2026-07-03
---

## Description

**What:** Author two documents-of-record that define the PROJECT-OS-PACK — the
canonical input contract a Founder hands to DasLab to bootstrap a new AI-agent
project — and the ADR that records the pack-format decision.

**Why:** ORGANISM WS7 GATEWAY needs a single, unambiguous, machine-readable
input contract so that any new project enters the org through one gate with a
manifest, a canonical lifecycle skeleton, discovery answers, and an approved
goal queue. Today the shape of a project's on-disk inputs is implicit and drifts
(e.g. qaqnuz's planning-doc names diverge from the lifecycle policy). This ticket
makes the pack format explicit and normative. This is GATE-1 Planning work for
WS7.

**Extend-vs-new:** NEW documents. There is no existing ADR or spec that defines
the project input contract. Extend the existing ADR index (add a row) and reuse
the existing spec template — do NOT fork them. The highest existing ADR is 0029,
so this authors 0030 (next in sequence).

**Key files + paths:**
- CREATE `docs/adr/0030-project-os-pack.md` — the pack-format decision record.
- CREATE `docs/specs/PROJECT-OS-PACK.md` — the input-contract spec.
- EDIT `docs/adr/README.md` — add the ADR-0030 index row + theme.
- READ `docs/adr/README.md` (index + conventions), `governance/policies/ai-agent-lifecycle.md`
  (§2 canonical `docs/01-planning` .. `docs/06-maintenance` skeleton — the source
  of truth, NOT qaqnuz's divergent names), `docs/specs/templates/SPEC.md`
  (spec template to follow), and `projects/qaqnuz/docs` (as a real-world example
  of a project on-disk layout — reference only, do not copy its divergent names).

**Manifest contract (define in the spec):** `projects/<name>/PROJECT-OS.yaml`
with fields: `name`, `mission`, `constraints`, `stack`, `budget`, `success
metrics`. Plus the canonical `docs/01-planning` .. `docs/06-maintenance`
skeleton, discovery answers, and `APPROVED-GOAL-QUEUE.md`.

**Constitution:** = QONUN laws + project-local constraints. Project-local
constraints NEVER relax org law; precedence follows ai-agent-lifecycle §1.5
(org law wins).

**Note on the ADR ticket:** the ADR-0030 ticket assignee is `chairman`; the
author of this decomposition/ticket is `ceo`.

## Acceptance criteria

- [ ] `docs/adr/0030-project-os-pack.md` authored + `docs/adr/README.md` index
  row (with theme) added.
- [ ] `docs/specs/PROJECT-OS-PACK.md` defines the `projects/<name>/PROJECT-OS.yaml`
  manifest (name, mission, constraints, stack, budget, success metrics) + the
  CANONICAL `docs/01-planning` .. `docs/06-maintenance` skeleton (from
  ai-agent-lifecycle §2, NOT qaqnuz's divergent names) + discovery answers +
  `APPROVED-GOAL-QUEUE.md`.
- [ ] Constitution = QONUN + project-local constraints, with project-local NEVER
  relaxing org law (precedence per §1.5).
- [ ] diagnostics 100/100.

## Log

### 2026-07-03 — CEO
Created from ORGANISM WS7 GATEWAY decomposition (/daslab-plan). Spec-of-record: docs/research/ORGANISM-PROGRAM-PLAN.md.
READ: docs/adr/README.md, governance/policies/ai-agent-lifecycle.md, docs/specs/templates/SPEC.md, projects/qaqnuz/docs.
Scope+acceptance (expand; keep frontmatter exact): GATE-1 Planning. (1) Author docs/adr/0030-project-os-pack.md (pack format decision; highest ADR is 0029 -> you author 0030; README row + theme). (2) Author docs/specs/PROJECT-OS-PACK.md defining the input contract: projects/<name>/PROJECT-OS.yaml manifest (name, mission, constraints, stack, budget, success metrics) + docs/01-planning .. 06-maintenance CANONICAL skeleton (from ai-agent-lifecycle.md §2, NOT qaqnuz's divergent names) + discovery answers + APPROVED-GOAL-QUEUE.md. Constitution = QONUN laws + project-local constraints (never relaxing org law; precedence §1.5). Set the ADR ticket assignee: chairman (author is ceo).
Acceptance: [ ] ADR-0030 + README row; [ ] docs/specs/PROJECT-OS-PACK.md defines the manifest + canonical 01-planning..06-maintenance skeleton + discovery + goal-queue; [ ] constitution = QONUN + project-local (never relaxes org law); [ ] diagnostics 100/100.
Constraints: org-engine ticket (this WS7 machinery), NO project: field.

### 2026-07-03 — CPO
Authored the two documents-of-record for the PROJECT-OS-PACK input contract (ORGANISM WS7 GATEWAY, O7-T01; GATE-1 Planning).
- CREATED `docs/adr/0030-project-os-pack.md` — the pack-format decision. Six binding invariants D-1…D-6: D-1 exactly one `projects/<name>/PROJECT-OS.yaml` manifest at the project root; D-2 closed manifest field set (`name`, `mission`, `constraints`, `stack`, `budget`, `success_metrics`); D-3 the CANONICAL AADL §2 `docs/01-planning…06-maintenance` six-stage skeleton, NOT qaqnuz's divergent names; D-4 Founder discovery answers (≥10 Q&A or waiver); D-5 Founder-approved `APPROVED-GOAL-QUEUE.md` (`APPROVED:`/`TASDIQLANDI:` via existing `check_approved_goal_queue.py`); D-6 Constitution = QONUN + project-local constraints, project-local NEVER relaxes org law (precedence = root AGENTS.md §2 + AADL scope note; org law wins on conflict; a relaxing pack is invalid). Numbering: plan text says "0029" but ADR ledger already assigned 0029 to guild-model, so this took the next free number 0030 (as ADR-0029's numbering note foreshadowed). Precedence: the ticket's "§1.5" has no literal home in AADL; read as a pointer to the real precedence law (root AGENTS.md §2 + AADL scope note) — noted explicitly in the ADR.
- EDITED `docs/adr/README.md` — added the ADR-0030 index row + a WS7 GATEWAY theme paragraph.
- CREATED `docs/specs/PROJECT-OS-PACK.md` — the field-level spec of record: the closed manifest schema (§3 with an illustrative non-normative example), the canonical skeleton (§4, explicitly not qaqnuz's names), discovery answers (§5), the approved goal queue (§6), the Constitution/precedence rule (§7), plus FR-001…FR-010 + SC-001…SC-005 as the testable surface O7-T02 `gateway_compile.py` binds to. Follows `docs/specs/templates/SPEC.md`.
- Constitution rule captured with a law-check: project-local may only tighten, never relax org law; a pack that waives a QONUN law / skips an AADL gate / self-grants never-auto-approve is invalid.
VERIFY (full, all green): `pytest -q` 1534 passed / 1 skipped; `diagnostics.py` 100/100; `board_lint.py` 0 violations (56 tickets); `ruff check scripts tests` clean.
Committed LOCAL-ONLY (strict no-push) on branch feat/das-1492-adr-0030-pack. Reviewer routing: CPO→CEO, but CEO authored this ticket → escalate one level to Chairman (ROUTING.md rule); assignee=chairman, status=in_review.

### 2026-07-03 — Chairman of the Board
GATE-1 sign-off review of the ADR-0030 + PROJECT-OS-PACK spec (WS7 GATEWAY, O7-T01). VERDICT: **PASS** — accepted, status → done.
Verified against acceptance + GATE-1, all green:
- **Manifest (D-1/D-2, spec §3.1):** exactly one `projects/<name>/PROJECT-OS.yaml` at the project root; closed field set present and complete — `name`, `mission`, `constraints`, `stack`, `budget`, `success_metrics`; unknown-key = warn, missing-required = actionable reject; `name`↔folder-segment equality enforced. Correct.
- **Canonical skeleton (D-3, spec §4):** cross-checked line-by-line against `ai-agent-lifecycle.md` §2 — the six folder names `01-planning`/`02-design`/`03-development`/`04-testing`/`05-deployment`/`06-maintenance` and each stage's per-artifact comment match §2 VERBATIM; qaqnuz's divergent names (`01-intake`/`02-prd`/`03-rfc`/…) explicitly excluded, with the AADL §2 `LIFECYCLE-MAP.md` escape correctly scoped to legacy migration only, not a new-pack licence. Correct.
- **Discovery (D-4, spec §5):** ≥10 Q&A or explicit waiver + sourced global research; open gate blocks compilation. Matches QONUN-3 + AADL §5. Correct.
- **Approved goal queue (D-5, spec §6):** `APPROVED-GOAL-QUEUE.md` required; `APPROVED:`/`TASDIQLANDI:` (`founder_approved`+) load-bearing via existing `check_approved_goal_queue.py`; compiled tickets go to the project board, never `board/tickets/`. Founder gate intact. Correct.
- **Constitution / precedence (D-6, spec §7):** QONUN + project-local, project-local may only tighten, org law wins on conflict, relaxing pack = invalid. The ticket's "§1.5" has no literal home in AADL; the CPO reconciled it to the real precedence law — I confirmed root `AGENTS.md` §2 line 29 VERBATIM ("lower-precedence may add constraints but never relax them set higher up") + the AADL scope note ("projects may add constraints, never relax them"). Citation accurate; reconciliation sound.
- **Traceability:** FR-001…FR-010 + SC-001…SC-005 present, each FR tagged to its D-x; spec follows `docs/specs/templates/SPEC.md`.
- **Numbering:** 0030 correct — 0029 is guild-model (Accepted 2026-07-03); numbering note explains the plan-text "0029" and the README ledger is authoritative.
- **README:** ADR-0030 index row + WS7 GATEWAY theme paragraph added; links resolve (`docs/adr/0030-*.md`, spec `../adr/0030-*.md`).
- **Placement law:** ADR + spec are platform docs under `docs/`; ticket carries no `project:` field — org-engine work, clean.
Gates (Chairman re-ran, all green): `diagnostics.py` **100/100**; `board_lint.py` **0 violations** (56 tickets); `pytest -q` **1553 passed / 1 skipped / 0 failed**.
No CHANGES required; no escalation. Sign-off committed LOCAL-ONLY (strict no-push).
