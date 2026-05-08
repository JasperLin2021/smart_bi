"""add sort_order to catalog_categories

Revision ID: 20260508_0021
Revises: 20260508_0020
Create Date: 2026-05-08
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260508_0021"
down_revision: Union[str, None] = "20260508_0020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table: str, col: str) -> bool:
    cols = [c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)]
    return col in cols


def upgrade() -> None:
    if not _has_column("catalog_categories", "sort_order"):
        op.add_column(
            "catalog_categories",
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        )


def downgrade() -> None:
    op.drop_column("catalog_categories", "sort_order")
