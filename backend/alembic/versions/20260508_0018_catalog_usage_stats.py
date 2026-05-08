"""add catalog usage stats

Revision ID: 20260508_0018
Revises: 20260508_0017
Create Date: 2026-05-08
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260508_0018"
down_revision: Union[str, None] = "20260508_0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def _has_column(table_name: str, column_name: str) -> bool:
    if not _has_table(table_name):
        return False
    return any(c["name"] == column_name for c in sa.inspect(op.get_bind()).get_columns(table_name))


def upgrade() -> None:
    if _has_table("data_assets") and not _has_column("data_assets", "view_count"):
        op.add_column(
            "data_assets",
            sa.Column("view_count", sa.Integer(), nullable=False, server_default="0"),
        )


def downgrade() -> None:
    if _has_column("data_assets", "view_count"):
        op.drop_column("data_assets", "view_count")
