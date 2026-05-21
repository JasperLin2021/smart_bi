"""user: add department field and dept_admin role support

Revision ID: 20260508_0025
Revises: 20260508_0024
Create Date: 2026-05-08
"""
from alembic import op
import sqlalchemy as sa

revision = "20260508_0025"
down_revision = "20260508_0024"
branch_labels = None
depends_on = None


def _has_table(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def _has_column(table_name: str, column_name: str) -> bool:
    if not _has_table(table_name):
        return False
    return any(column["name"] == column_name for column in sa.inspect(op.get_bind()).get_columns(table_name))


def upgrade():
    if _has_table("users") and not _has_column("users", "department"):
        op.add_column("users", sa.Column("department", sa.String(64), nullable=True))


def downgrade():
    if _has_column("users", "department"):
        op.drop_column("users", "department")
