"""baseline existing smart bi schema

Revision ID: 20260429_0001
Revises:
Create Date: 2026-04-29
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260429_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Existing deployments were created by SQLAlchemy metadata on startup. This
    # minimal baseline creates the legacy metrics table when migrations run on a
    # fresh database before the application has started.
    bind = op.get_bind()
    metrics = sa.Table(
        "metrics",
        sa.MetaData(),
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("datasource_id", sa.Integer(), nullable=True, index=True),
        sa.Column("name", sa.String(length=128), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("definition", sa.Text(), nullable=False),
        sa.Column("table_name", sa.String(length=64), nullable=True),
        sa.Column("column_name", sa.String(length=64), nullable=True),
        sa.Column("formula", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Integer(), server_default="1", nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
    )
    metrics.create(bind, checkfirst=True)
    sa.Index("ix_metrics_id", metrics.c.id).create(bind, checkfirst=True)
    sa.Index("ix_metrics_datasource_id", metrics.c.datasource_id).create(bind, checkfirst=True)


def downgrade() -> None:
    pass
