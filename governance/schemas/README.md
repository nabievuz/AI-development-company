# Artifact-schema registry (`governance/schemas/`)

Typed input/output contracts for board tickets (DAS-1467).

A ticket may declare, in its frontmatter, what artifact it hands downstream and
what it expects upstream:

```yaml
produces: task-ledger
consumes: [typed-contracts, task-ledger]
```

Each name resolves to a schema file in this directory: `produces: task-ledger`
requires `governance/schemas/task-ledger.yaml`. The file stem MUST equal the
schema `name`. This lets a producer/consumer pair be checked at plan time rather
than inferred from prose at run time.

## File grammar

```yaml
name: task-ledger          # REQUIRED, non-empty; MUST equal the file stem
version: 1                 # OPTIONAL int >= 1 (default 1)
description: <one line>    # REQUIRED, non-empty
fields:                    # REQUIRED, non-empty list
  - name: run_id           #   REQUIRED field name (non-empty)
    type: string           #   REQUIRED, one of: string integer number boolean object array
    required: true         #   OPTIONAL bool (default false)
    description: <text>    #   OPTIONAL
```

## Single source of truth

The schema shape is owned by `scripts/artifact_schemas.py` — pydantic-backed when
pydantic is installed, with a faithful stdlib fallback that enforces the identical
constraints (DasLab's runtime is stdlib + PyYAML only). `scripts/board_lint.py`
rule R11 imports that loader and fails any ticket whose `produces:` / `consumes:`
names an unknown or malformed schema. Absent fields lint exactly as before
(additive).

## Validators

- `python3 scripts/board_lint.py` — R11 validates every ticket's `produces:` /
  `consumes:` against this registry.
- `python3 -m pytest tests/test_artifact_schemas.py tests/test_board_lint.py`
