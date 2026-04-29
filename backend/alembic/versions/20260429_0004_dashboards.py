"""add dashboard center

Revision ID: 20260429_0004
Revises: 20260429_0003
Create Date: 2026-04-29
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260429_0004"
down_revision: Union[str, None] = "20260429_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "dashboards",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("layout_json", sa.JSON(), nullable=True),
        sa.Column("filters_json", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column("visibility", sa.String(length=32), nullable=False, server_default="private"),
        sa.Column("org_id", sa.Integer(), nullable=True),
        sa.Column("owner_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_dashboards_id"), "dashboards", ["id"], unique=False)
    op.create_index(op.f("ix_dashboards_title"), "dashboards", ["title"], unique=False)
    op.create_index(op.f("ix_dashboards_status"), "dashboards", ["status"], unique=False)
    op.create_index(op.f("ix_dashboards_org_id"), "dashboards", ["org_id"], unique=False)
    op.create_index(op.f("ix_dashboards_owner_id"), "dashboards", ["owner_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_dashboards_owner_id"), table_name="dashboards")
    op.drop_index(op.f("ix_dashboards_org_id"), table_name="dashboards")
    op.drop_index(op.f("ix_dashboards_status"), table_name="dashboards")
    op.drop_index(op.f("ix_dashboards_title"), table_name="dashboards")
    op.drop_index(op.f("ix_dashboards_id"), table_name="dashboards")
    op.drop_table("dashboards")
