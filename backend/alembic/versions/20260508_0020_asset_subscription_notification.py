"""add asset subscription and notification

Revision ID: 20260508_0020
Revises: 20260508_0019
Create Date: 2026-05-08
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260508_0020"
down_revision: Union[str, None] = "20260508_0019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def _has_index(table_name: str, index_name: str) -> bool:
    if not _has_table(table_name):
        return False
    return any(i["name"] == index_name for i in sa.inspect(op.get_bind()).get_indexes(table_name))


def upgrade() -> None:
    if not _has_table("asset_subscriptions"):
        op.create_table(
            "asset_subscriptions",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("asset_id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["asset_id"], ["data_assets.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", "asset_id", name="uq_asset_subscription"),
        )
    for col in ("id", "user_id", "asset_id"):
        idx = f"ix_asset_subscriptions_{col}"
        if not _has_index("asset_subscriptions", idx):
            op.create_index(idx, "asset_subscriptions", [col], unique=False)

    if not _has_table("asset_notifications"):
        op.create_table(
            "asset_notifications",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("asset_id", sa.Integer(), nullable=False),
            sa.Column("message", sa.Text(), nullable=False),
            sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["asset_id"], ["data_assets.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
    for col in ("id", "user_id", "asset_id", "is_read"):
        idx = f"ix_asset_notifications_{col}"
        if not _has_index("asset_notifications", idx):
            op.create_index(idx, "asset_notifications", [col], unique=False)


def downgrade() -> None:
    for table_name in ("asset_notifications", "asset_subscriptions"):
        if _has_table(table_name):
            op.drop_table(table_name)
