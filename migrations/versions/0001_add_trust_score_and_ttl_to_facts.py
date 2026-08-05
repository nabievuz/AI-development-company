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


    op.add_column(_TABLE, sa.Column("trust_score", sa.Float(), nullable=False, server_default="0.5"))
    op.add_column(_TABLE, sa.Column("ttl", sa.Integer(), nullable=True))


def downgrade() -> None:


    with op.batch_alter_table(_TABLE, table_kwargs={"sqlite_autoincrement": True}) as batch_op:
        batch_op.drop_column("ttl")
        batch_op.drop_column("trust_score")
