"""add dashboard_comments and rls_rules tables

Revision ID: 20260506_0013
Revises: 20260430_0012
Create Date: 2026-05-06
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "20260506_0013"
down_revision: Union[str, None] = "20260430_0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "dashboard_comments",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("dashboard_id", sa.Integer(), sa.ForeignKey("dashboards.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(64), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "rls_rules",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("datasource_id", sa.Integer(), sa.ForeignKey("datasources.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("org_id", sa.Integer(), nullable=True, index=True),
        sa.Column("user_id", sa.Integer(), nullable=True, index=True),
        sa.Column("table_name", sa.String(128), nullable=False),
        sa.Column("column_name", sa.String(128), nullable=False),
        sa.Column("operator", sa.String(16), nullable=False, server_default="="),
        sa.Column("filter_value", sa.String(512), nullable=False),
        sa.Column("is_active", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("rls_rules")
    op.drop_table("dashboard_comments")
