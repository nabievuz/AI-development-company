---
id: DAS-1467
title: Typed produces and consumes ticket contracts with pydantic schemas
status: done
assignee: cto
author: ceo
dept: engineering
priority: p1
parent: DAS-1463
goal: organism-ws2-loom
depends_on: [DAS-1464]
zone: board-lint-schema
created: 2026-07-03
updated: 2026-07-03
---

## Description

### What & why
GATE-2/3 (P8) of the ORGANISM WS2 LOOM program. Today a board ticket declares
what it depends on (`depends_on:`) but there is no machine-readable statement of
what artifact a ticket **produces** or **consumes**. Downstream synthesis
tickets (e.g. DAS-1468) have to infer, by prose, what an upstream ticket handed
them. This ticket introduces two OPTIONAL frontmatter fields — `produces:` and
`consumes:` — that name **artifact schemas** defined once, centrally, in
`governance/schemas/*.yaml` and backed by pydantic models. board_lint then
validates that every named schema exists and is well-formed, closing the loop so
a ticket's inputs/outputs are a typed contract rather than a comment.

This is the LOOM's typed-contract layer: it lets a producer/consumer pair be
checked at plan time (does the artifact the consumer wants actually get produced,
and does its shape match the declared schema?) instead of at run time.

### Embedded context (so work needs no re-discovery)
- **Frontmatter parsing is NOT YAML.** There are three independent frontmatter
  parsers in the repo and they must be reconciled, not bypassed:
  1. `scripts/board_lint.py` — regex parser: `_FM_RE` (grabs the `---…---` block)
     + `_KV_RE` (`^key: value$` per line, captures each value as a raw string).
     It has tolerant single-field readers `_zone_of()` / `_merge_policy_of()`
     that strip whitespace + inline quotes. List-valued fields like
     `depends_on: [DAS-1464]` are captured as the raw string `[DAS-1464]` — the
     KV parser does NOT split lists.
  2. `scripts/check_dependency_graph.py` — its own `_fm_field()` line reader that
     pulls one field, then `DAS_RE.findall()` to extract ids from a list value.
     This is the pattern to imitate for parsing a bracketed/comma list tolerantly.
  3. `board/README.md` documents the schema humans/agents follow.
- **Precedent to imitate — merge_policy (R10).** merge_policy was added exactly
  the way this field should be: OPTIONAL + additive (tickets without it lint
  unchanged), grammar owned by a single source-of-truth module
  (`scripts/merge_reducers.py::is_valid_policy`), validated **in place** inside
  `board_lint.lint_tickets()` under a new rule guarded by `if "field" in fm:`.
  Follow that shape — do NOT create a parallel validator script.
- **depends_on precedent** shows the tolerant list-read: `check_dependency_graph`
  reads `depends_on` as a raw string and regex-extracts the ids. Add a matching
  tolerant reader in board_lint for the new list-ish fields (a `produces:` /
  `consumes:` value may be a single schema name or a bracketed list of names).
- **board_lint rules R1–R10** live in `lint_tickets()`; add the new rule there,
  numbered/commented consistently, so there is one validator, not two.
- **Optional-fields table** in `board/README.md` (the `| Field | Example |
  Meaning |` table around lines 65–76) is where the two new fields get their
  human documentation row.

### Extend vs new
- **EXTEND** `scripts/board_lint.py` in place — add a tolerant reader for
  `produces:`/`consumes:` (mirroring `_zone_of` / `check_dependency_graph._fm_field`)
  and a new lettered rule inside `lint_tickets()`. No parallel validator.
- **EXTEND** `board/README.md` optional-fields table with two rows.
- **NEW** `governance/schemas/` directory holding the pydantic-backed artifact
  schema files (`*.yaml`) + the small pydantic loader/validator module that
  board_lint imports (single source of truth for schema shape, like
  `merge_reducers.py` is for policy grammar). Ship at least two example artifact
  schemas.
- **NEW** tests covering parse + validation + the negative cases.

### Key files (paths)
- `scripts/board_lint.py` — extend: tolerant `produces:`/`consumes:` reader +
  new validation rule in `lint_tickets()`; reconcile with the regex parser.
- `scripts/check_dependency_graph.py` — reference for the tolerant list reader
  (`_fm_field` + `DAS_RE.findall`); reconcile the three parsers if you touch it.
- `scripts/merge_reducers.py` — reference precedent (`is_valid_policy` single
  source of truth); the schema loader/validator module should mirror this shape.
- `board/README.md` — add two optional-field rows (`produces` / `consumes`).
- `governance/schemas/*.yaml` — NEW artifact schema definitions (pydantic-backed).
- `governance/schemas/<loader>.py` (or equivalent) — NEW pydantic loader that
  board_lint imports to validate the named schemas.
- `docs/specs/templates/SPEC.md` — reference for spec-of-record conventions.
- tests under the repo's existing test tree — NEW parse/validation coverage.

## Acceptance criteria
- [ ] `produces:` / `consumes:` OPTIONAL frontmatter fields are parsed AND
      validated by board_lint (present-but-unknown schema name = FAIL; absent =
      lints exactly as before — additive).
- [ ] `governance/schemas/*.yaml` exists with at least two example artifact
      schemas, each pydantic-backed (a pydantic model is the single source of
      truth for the schema shape / grammar).
- [ ] board_lint is extended **in place** — the new rule lives inside
      `lint_tickets()` alongside R1–R10; NO parallel/second validator script.
- [ ] The new fields are read with a **tolerant** reader (strips whitespace +
      inline quotes; accepts a single schema name or a bracketed/comma list),
      mirroring `_zone_of` / `check_dependency_graph._fm_field`; the three
      frontmatter parsers are reconciled (or the new reader documented as the
      tolerant path for these fields).
- [ ] `board/README.md` optional-fields table documents `produces:` and
      `consumes:` (example + meaning rows).
- [ ] Tests cover: valid produce/consume, unknown schema name (FAIL), malformed
      schema yaml (FAIL), and the additive no-op (ticket without the fields).
- [ ] Full suite: 0 failed; diagnostics 100/100.

## Produces
- `typed-contracts` — the `produces:`/`consumes:` frontmatter + the
  `governance/schemas/` pydantic-backed artifact schema registry. Consumed by
  DAS-1468.

## Constraints
- org-engine ticket: NO `project:` field (board_lint R9 fails any org-board
  ticket that declares one).
- Frontmatter block above must stay exactly as given.

## Log
### 2026-07-03 — CEO
Created from ORGANISM WS2 LOOM decomposition (/daslab-plan). Spec-of-record:
docs/research/ORGANISM-PROGRAM-PLAN.md. Read scripts/board_lint.py,
scripts/check_dependency_graph.py, board/README.md, docs/specs/templates/SPEC.md
before implementing — the three frontmatter parsers (board_lint regex `_KV_RE`,
check_dependency_graph `_fm_field`, and the human schema in board/README.md) must
be reconciled, and the new fields must follow the merge_policy precedent:
OPTIONAL/additive, grammar owned by one source-of-truth module, validated in
place inside `lint_tickets()`.

### 2026-07-03 — Backend EM
Implemented the typed produce/consume contract layer. Changes:
- NEW `scripts/artifact_schemas.py` — single source of truth for the artifact
  -schema shape, mirroring the `merge_reducers.py` precedent. Pydantic-backed:
  `ArtifactField` / `ArtifactSchema` pydantic models are authoritative WHEN
  pydantic is importable. Because DasLab's runtime is deliberately stdlib+PyYAML
  only (`requirements.in`) and pydantic is not installed (and cannot be, PEP 668
  externally-managed env), the module falls back to an equivalent stdlib dataclass
  validator enforcing the IDENTICAL constraints (shared `ALLOWED_FIELD_TYPES`,
  required-key rules, name==file-stem). `HAVE_PYDANTIC` records the active path.
  Exposes `load_schema_file` / `available_schema_names` / `schema_registry` /
  `schema_path` and raises `SchemaError` on any malformed schema.
- NEW `governance/schemas/` with two example artifact schemas
  (`task-ledger.yaml`, `typed-contracts.yaml`) + a human `README.md`.
- EXTENDED `scripts/board_lint.py` IN PLACE — added tolerant reader
  `_schema_names_of()` (mirrors `_zone_of` / `check_dependency_graph._fm_field`:
  strips brackets/whitespace/inline quotes, accepts single name or comma/bracket
  list — the reconciled parse path for these list-ish fields the regex `_KV_RE`
  can't split) and new rule R11 inside `lint_tickets()` (unknown schema = FAIL,
  malformed schema file = FAIL, present-but-empty = FAIL, absent = additive
  no-op). New optional `schemas_dir` param (defaults to governance/schemas/).
- EXTENDED `board/README.md` optional-fields table with `produces` / `consumes`
  rows, and board_lint's module docstring rule list (R11).
- NEW tests: `tests/test_artifact_schemas.py` (14) + R11/tolerant-reader cases
  appended to `tests/test_board_lint.py`.
VERIFY (full suite, all green): `pytest -q` = 1133 passed / 1 skipped;
`scripts/diagnostics.py` = 100/100; `scripts/board_lint.py` = 0 violations;
`scripts/check_dependency_graph.py` = clean; `ruff check scripts tests` = clean;
`check_links.py` = clean. Committed LOCAL only (strict local-only; no push/PR).
Reviewer = CTO (backend-em manager per ROUTING.md). Note for review: the
pydantic-vs-stdlib reconciliation is a deliberate call given the env cannot
install pydantic — flagging for CTO sign-off.

### 2026-07-03 — Orchestrator (/daslab-cycle collect)
Done via local-only done-gate: full suite 1201 pass + validators green + merge verification. produces/consumes + board_lint R11 + governance/schemas/ + artifact_schemas.py (pydantic-backed with faithful stdlib fallback — pydantic not installable in this env, acceptable).
