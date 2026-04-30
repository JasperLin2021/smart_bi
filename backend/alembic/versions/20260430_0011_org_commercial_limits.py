"""add organization commercial limits

Revision ID: 20260430_0011
Revises: 20260430_0010
Create Date: 2026-04-30
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260430_0011"
down_revision: Union[str, None] = "20260430_0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def _has_column(table_name: str, column_name: str) -> bool:
    if not _has_table(table_name):
        return False
    return any(column["name"] == column_name for column in sa.inspect(op.get_bind()).get_columns(table_name))


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    if _has_table(table_name) and not _has_column(table_name, column.name):
        op.add_column(table_name, column)


def upgrade() -> None:
    _add_column_if_missing("organizations", sa.Column("plan_type", sa.String(length=32), server_default="team", nullable=False))
    _add_column_if_missing("organizations", sa.Column("user_limit", sa.Integer(), nullable=True))
    _add_column_if_missing("organizations", sa.Column("datasource_limit", sa.Integer(), nullable=True))
    _add_column_if_missing("organizations", sa.Column("dashboard_limit", sa.Integer(), nullable=True))
    _add_column_if_missing("organizations", sa.Column("big_screen_limit", sa.Integer(), nullable=True))
    _add_column_if_missing("organizations", sa.Column("monthly_query_limit", sa.Integer(), nullable=True))
    _add_column_if_missing("organizations", sa.Column("white_label_enabled", sa.Integer(), server_default="0", nullable=False))
    _add_column_if_missing("organizations", sa.Column("branding_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    if not _has_table("organizations"):
        return
    for column_name in [
        "branding_json",
        "white_label_enabled",
        "monthly_query_limit",
        "big_screen_limit",
        "dashboard_limit",
        "datasource_limit",
        "user_limit",
        "plan_type",
    ]:
        if _has_column("organizations", column_name):
            op.drop_column("organizations", column_name)
