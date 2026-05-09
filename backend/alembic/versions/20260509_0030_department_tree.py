"""organization: add department tree

Revision ID: 20260509_0030
Revises: 20260508_0025
Create Date: 2026-05-09 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260509_0030"
down_revision = "20260508_0025"
branch_labels = None
depends_on = None


def _has_table(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return inspector.has_table(table_name)


def _has_column(table_name: str, column_name: str) -> bool:
    if not _has_table(table_name):
        return False
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def upgrade() -> None:
    if not _has_table("departments"):
        op.create_table(
            "departments",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(length=128), nullable=False),
            sa.Column("org_id", sa.Integer(), nullable=False),
            sa.Column("parent_id", sa.Integer(), nullable=True),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        )
        op.create_index("ix_departments_id", "departments", ["id"])
        op.create_index("ix_departments_org_id", "departments", ["org_id"])
        op.create_index("ix_departments_parent_id", "departments", ["parent_id"])

    if _has_table("users") and not _has_column("users", "department_id"):
        op.add_column("users", sa.Column("department_id", sa.Integer(), nullable=True))
        op.create_index("ix_users_department_id", "users", ["department_id"])


def downgrade() -> None:
    if _has_table("users") and _has_column("users", "department_id"):
        op.drop_index("ix_users_department_id", table_name="users")
        op.drop_column("users", "department_id")
    if _has_table("departments"):
        op.drop_index("ix_departments_parent_id", table_name="departments")
        op.drop_index("ix_departments_org_id", table_name="departments")
        op.drop_index("ix_departments_id", table_name="departments")
        op.drop_table("departments")
