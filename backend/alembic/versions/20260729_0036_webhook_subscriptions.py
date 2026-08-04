"""create webhook subscriptions table

Revision ID: 20260729_0036
Revises: 20260521_0035
Create Date: 2026-07-29
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260729_0036"
down_revision: Union[str, None] = "20260521_0035"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def upgrade() -> None:
    if not _has_table("webhook_subscriptions"):
        op.create_table(
            "webhook_subscriptions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("org_id", sa.Integer(), nullable=True, index=True),
            sa.Column("name", sa.String(120), nullable=False, index=True),
            sa.Column("target_url", sa.String(512), nullable=False),
            sa.Column("events", sa.JSON(), nullable=False),
            sa.Column("secret", sa.String(256), nullable=True),
            sa.Column("enabled", sa.Integer(), nullable=False, server_default="1", index=True),
            sa.Column("created_by", sa.Integer(), nullable=True, index=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        )


def downgrade() -> None:
    if _has_table("webhook_subscriptions"):
        op.drop_table("webhook_subscriptions")
