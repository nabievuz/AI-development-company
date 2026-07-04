# ArcRift schema migrations — Alembic (E-004 R-13 / ADR-010)

Prisma-Migrate's **discipline** for ArcRift's SQLite, Python-native via Alembic
(ADR-010, extending ADR-005). ADR-009 rejects the Prisma *tool* (a Node toolchain);
this directory adopts the *pattern*: declarative migrations, a version history with
checksums, shadow-database validation, explicit data-loss evaluation, and a working
`downgrade()`.

## Hard rules

- **Never-auto-approve.** Every migration here is a Critical / QONUN-5
  `schema_migration` (matched by `**/migrations/**` in `config/risk_taxonomy.yaml`).
  A human **Founder** applies it to the real ArcRift database; the engine never auto-
  or self-approves, and CI never applies it to the live DB.
- **Reversible.** A working `downgrade()` is mandatory — it *is* the ADR-005 rollback
  drill. SQLite lacked native `DROP COLUMN` before 3.35, so downgrades use
  `op.batch_alter_table` (a safe table rebuild); `render_as_batch=True` is set in
  `env.py`.
- **Data-loss evaluated.** Each revision's docstring states whether `upgrade()` /
  `downgrade()` is additive or destructive before it runs.
- **Pinned deps.** `alembic` + `SQLAlchemy` are pinned in `requirements-dev.txt`
  (both MIT, LAW 9). They are dev/CI + apply-time tools, not engine runtime deps.

## Shadow-database validation (CI)

`tests/test_arcrift_migration.py` is the shadow check: it seeds a **disposable** SQLite
with ArcRift's pre-migration `facts` table, runs `upgrade` → asserts the new columns
exist and no fact rows are lost, then runs `downgrade` → asserts the columns are gone and
the original schema + rows survive. It never touches `~/ArcRift/backend/ArcRift.db`. The
test self-skips when Alembic is not installed (local dev) and runs in CI.

## Revisions

- `0001_add_trust_score_and_ttl_to_facts` — adds `trust_score` (REAL, neutral default
  0.5) and `ttl` (INTEGER, nullable = no expiry) to `facts`, per ADR-005 memory
  governance (trust-weighted, TTL-bounded recall). The first Critical/QONUN-5 approval
  of P3.

## Applying a migration (human Founder, against the real DB)

Supply the real database URL explicitly — it is **not** hard-coded (`alembic.ini` ships
an inert in-memory placeholder):

    # dry run — emit SQL only, apply nothing
    alembic -x url=sqlite:////absolute/path/to/ArcRift.db upgrade head --sql

    # apply (only after Founder approval + a fresh backup)
    alembic -x url=sqlite:////absolute/path/to/ArcRift.db upgrade head

    # rollback drill
    alembic -x url=sqlite:////absolute/path/to/ArcRift.db downgrade -1

(`env.py` reads `-x url=...` when provided, else falls back to `sqlalchemy.url`.)
