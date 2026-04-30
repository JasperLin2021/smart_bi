"""add legacy compatibility columns

Revision ID: 20260429_0005
Revises: 20260429_0004
Create Date: 2026-04-29
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260429_0005"
down_revision: Union[str, None] = "20260429_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(inspector: sa.Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _has_column(inspector: sa.Inspector, table_name: str, column_name: str) -> bool:
    if not _has_table(inspector, table_name):
        return False
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def _add_column_if_missing(inspector: sa.Inspector, table_name: str, column: sa.Column) -> None:
    if _has_table(inspector, table_name) and not _has_column(inspector, table_name, column.name):
        op.add_column(table_name, column)


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    _add_column_if_missing(inspector, "users", sa.Column("data_scope", sa.String(length=32), nullable=True))
    _add_column_if_missing(
        inspector,
        "users",
        sa.Column("permission_override_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    _add_column_if_missing(inspector, "users", sa.Column("menu_permissions", sa.Text(), nullable=True))
    _add_column_if_missing(inspector, "users", sa.Column("action_permissions", sa.Text(), nullable=True))

    _add_column_if_missing(inspector, "query_history", sa.Column("parent_history_id", sa.Integer(), nullable=True))
    _add_column_if_missing(inspector, "query_history", sa.Column("llm_model", sa.String(length=128), nullable=True))


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    for table_name, column_name in (
        ("query_history", "llm_model"),
        ("query_history", "parent_history_id"),
        ("users", "action_permissions"),
        ("users", "menu_permissions"),
        ("users", "permission_override_enabled"),
        ("users", "data_scope"),
    ):
        if _has_column(inspector, table_name, column_name):
            op.drop_column(table_name, column_name)
