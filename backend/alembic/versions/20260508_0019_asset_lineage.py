"""add asset lineage

Revision ID: 20260508_0019
Revises: 20260508_0018
Create Date: 2026-05-08
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260508_0019"
down_revision: Union[str, None] = "20260508_0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def _has_index(table_name: str, index_name: str) -> bool:
    if not _has_table(table_name):
        return False
    return any(i["name"] == index_name for i in sa.inspect(op.get_bind()).get_indexes(table_name))


def upgrade() -> None:
    if not _has_table("asset_lineage"):
        op.create_table(
            "asset_lineage",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("source_id", sa.Integer(), nullable=False),
            sa.Column("target_id", sa.Integer(), nullable=False),
            sa.Column("rel_type", sa.String(length=32), nullable=False, server_default="derives_from"),
            sa.Column("org_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
            sa.ForeignKeyConstraint(["source_id"], ["data_assets.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["target_id"], ["data_assets.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("source_id", "target_id", name="uq_asset_lineage"),
        )
    for col in ("id", "source_id", "target_id", "org_id"):
        idx = f"ix_asset_lineage_{col}"
        if not _has_index("asset_lineage", idx):
            op.create_index(idx, "asset_lineage", [col], unique=False)


def downgrade() -> None:
    if _has_table("asset_lineage"):
        op.drop_table("asset_lineage")
