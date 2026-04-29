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
    op.add_column("metrics", sa.Column("owner_name", sa.String(length=128), nullable=True))
    op.add_column("metrics", sa.Column("unit", sa.String(length=32), nullable=True))
    op.add_column("metrics", sa.Column("aggregation", sa.String(length=32), nullable=False, server_default="sum"))
    op.add_column("metrics", sa.Column("tags", sa.JSON(), nullable=True))
    op.add_column("metrics", sa.Column("status", sa.String(length=32), nullable=False, server_default="published"))
    op.add_column("metrics", sa.Column("dimensions", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("metrics", "dimensions")
    op.drop_column("metrics", "status")
    op.drop_column("metrics", "tags")
    op.drop_column("metrics", "aggregation")
    op.drop_column("metrics", "unit")
    op.drop_column("metrics", "owner_name")
