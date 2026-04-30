"""add audit logs

Revision ID: 20260429_0006
Revises: 20260429_0005
Create Date: 2026-04-29
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260429_0006"
down_revision: Union[str, None] = "20260429_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    audit_logs = sa.Table(
        "audit_logs",
        sa.MetaData(),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("actor_username", sa.String(length=128), nullable=True),
        sa.Column("actor_role", sa.String(length=32), nullable=True),
        sa.Column("org_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=False),
        sa.Column("resource_id", sa.String(length=128), nullable=True),
        sa.Column("resource_name", sa.String(length=256), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="success"),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("detail_json", sa.Text(), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    audit_logs.create(op.get_bind(), checkfirst=True)
    for column in (
        "id",
        "actor_user_id",
        "org_id",
        "action",
        "resource_type",
        "resource_id",
        "status",
        "created_at",
    ):
        sa.Index(op.f(f"ix_audit_logs_{column}"), audit_logs.c[column]).create(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    for column in (
        "created_at",
        "status",
        "resource_id",
        "resource_type",
        "action",
        "org_id",
        "actor_user_id",
        "id",
    ):
        op.drop_index(op.f(f"ix_audit_logs_{column}"), table_name="audit_logs")
    op.drop_table("audit_logs")
