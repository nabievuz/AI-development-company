"""add trust_score and ttl to ArcRift facts (ADR-005 governance; ADR-010 discipline).

Revision ID: 0001_trust_score_ttl
Revises:
Create Date: 2026-06-22

ADR-005 governs ArcRift recall with TTL (per-type lifespan) + trust-score (provenance
weighting: verified PR > review-validated > unverified claim). Adding these two columns
to the existing ArcRift ``facts`` table is a Critical / QONUN-5 ``schema_migration`` —
never-auto-approve; a human Founder applies it to the live DB, the engine never does.

DATA-LOSS EVALUATION (required by ADR-010 before any destructive change):
  - upgrade(): ADDITIVE only. ``trust_score`` backfills existing rows with a neutral 0.5
    (unverified until re-scored); ``ttl`` is nullable (NULL = no expiry). No existing data
    is read, rewritten, or dropped. Safe.
  - downgrade(): DROPS both columns — this IS the ADR-005 rollback drill. It discards any
    trust_score/ttl written after the upgrade (destructive BY DESIGN as the rollback);
    fact rows (subject/relation/object) are preserved. SQLite lacked native DROP COLUMN
    before 3.35, so batch_alter_table rebuilds the table to keep the downgrade reversible.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_trust_score_ttl"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "facts"


def upgrade() -> None:
    # Additive, non-destructive. server_default backfills existing rows with a neutral
    # (unverified) trust score; ttl NULL means "no expiry" until a lifespan is set.
    op.add_column(_TABLE, sa.Column("trust_score", sa.Float(), nullable=False, server_default="0.5"))
    op.add_column(_TABLE, sa.Column("ttl", sa.Integer(), nullable=True))


def downgrade() -> None:
    # The ADR-005 rollback drill. batch_alter_table => SQLite-safe table rebuild so the
    # column drops are reversible on the ArcRift SQLite backend. Fact rows, the FK, and both
    # indexes are preserved by reflection. table_kwargs sqlite_autoincrement=True is REQUIRED:
    # SQLAlchemy reflection cannot recover SQLite's AUTOINCREMENT keyword, so without it the
    # rebuild would silently downgrade `id INTEGER PRIMARY KEY AUTOINCREMENT` to a plain rowid
    # PK — letting a deleted max id be reused on the next insert (a fact-id reference could
    # then rebind to a different fact). This keeps the rollback faithful to ArcRift's schema.
    with op.batch_alter_table(_TABLE, table_kwargs={"sqlite_autoincrement": True}) as batch_op:
        batch_op.drop_column("ttl")
        batch_op.drop_column("trust_score")
