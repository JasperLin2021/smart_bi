"""add metric semantic fields

Revision ID: 20260429_0002
Revises: 20260429_0001
Create Date: 2026-04-29
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260429_0002"
down_revision: Union[str, None] = "20260429_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    existing = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("metrics")}
    columns = [
        sa.Column("owner_name", sa.String(length=128), nullable=True),
        sa.Column("unit", sa.String(length=32), nullable=True),
        sa.Column("aggregation", sa.String(length=32), nullable=False, server_default="sum"),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="published"),
        sa.Column("dimensions", sa.JSON(), nullable=True),
    ]
    for column in columns:
        if column.name not in existing:
            op.add_column("metrics", column)


def downgrade() -> None:
    op.drop_column("metrics", "dimensions")
    op.drop_column("metrics", "status")
    op.drop_column("metrics", "tags")
    op.drop_column("metrics", "aggregation")
    op.drop_column("metrics", "unit")
    op.drop_column("metrics", "owner_name")
