"""add data assets catalog

Revision ID: 20260429_0003
Revises: 20260429_0002
Create Date: 2026-04-29
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260429_0003"
down_revision: Union[str, None] = "20260429_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    data_assets = sa.Table(
        "data_assets",
        sa.MetaData(),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("asset_type", sa.String(length=32), nullable=False),
        sa.Column("asset_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("datasource_id", sa.Integer(), nullable=True),
        sa.Column("org_id", sa.Integer(), nullable=True),
        sa.Column("owner_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    data_assets.create(bind, checkfirst=True)
    for column in ("id", "asset_type", "asset_id", "name", "datasource_id", "org_id", "owner_id", "status"):
        sa.Index(op.f(f"ix_data_assets_{column}"), data_assets.c[column]).create(bind, checkfirst=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_data_assets_status"), table_name="data_assets")
    op.drop_index(op.f("ix_data_assets_owner_id"), table_name="data_assets")
    op.drop_index(op.f("ix_data_assets_org_id"), table_name="data_assets")
    op.drop_index(op.f("ix_data_assets_datasource_id"), table_name="data_assets")
    op.drop_index(op.f("ix_data_assets_name"), table_name="data_assets")
    op.drop_index(op.f("ix_data_assets_asset_id"), table_name="data_assets")
    op.drop_index(op.f("ix_data_assets_asset_type"), table_name="data_assets")
    op.drop_index(op.f("ix_data_assets_id"), table_name="data_assets")
    op.drop_table("data_assets")
