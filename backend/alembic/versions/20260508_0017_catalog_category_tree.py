"""add catalog category tree

Revision ID: 20260508_0017
Revises: 20260507_0016
Create Date: 2026-05-08
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260508_0017"
down_revision: Union[str, None] = "20260507_0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def _has_column(table_name: str, column_name: str) -> bool:
    if not _has_table(table_name):
        return False
    return any(c["name"] == column_name for c in sa.inspect(op.get_bind()).get_columns(table_name))


def _has_index(table_name: str, index_name: str) -> bool:
    if not _has_table(table_name):
        return False
    return any(i["name"] == index_name for i in sa.inspect(op.get_bind()).get_indexes(table_name))


def upgrade() -> None:
    if not _has_table("catalog_categories"):
        op.create_table(
            "catalog_categories",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=128), nullable=False),
            sa.Column("parent_id", sa.Integer(), nullable=True),
            sa.Column("org_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
            sa.ForeignKeyConstraint(["parent_id"], ["catalog_categories.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
    for col in ("id", "parent_id", "org_id"):
        idx = f"ix_catalog_categories_{col}"
        if not _has_index("catalog_categories", idx):
            op.create_index(idx, "catalog_categories", [col], unique=False)

    if _has_table("data_assets") and not _has_column("data_assets", "category_id"):
        op.add_column("data_assets", sa.Column("category_id", sa.Integer(), nullable=True))
        op.create_foreign_key(
            "fk_data_assets_category_id",
            "data_assets",
            "catalog_categories",
            ["category_id"],
            ["id"],
            ondelete="SET NULL",
        )
        if not _has_index("data_assets", "ix_data_assets_category_id"):
            op.create_index("ix_data_assets_category_id", "data_assets", ["category_id"], unique=False)


def downgrade() -> None:
    if _has_column("data_assets", "category_id"):
        op.drop_index("ix_data_assets_category_id", table_name="data_assets")
        op.drop_constraint("fk_data_assets_category_id", "data_assets", type_="foreignkey")
        op.drop_column("data_assets", "category_id")
    if _has_table("catalog_categories"):
        op.drop_table("catalog_categories")
