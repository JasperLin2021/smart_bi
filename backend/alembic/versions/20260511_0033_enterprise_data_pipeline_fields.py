"""add enterprise data pipeline governance fields

Revision ID: 20260511_0033
Revises: 20260511_0032
Create Date: 2026-05-11
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260511_0033"
down_revision: Union[str, None] = "20260511_0032"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def _has_column(table_name: str, column_name: str) -> bool:
    if not _has_table(table_name):
        return False
    return any(column["name"] == column_name for column in sa.inspect(op.get_bind()).get_columns(table_name))


def upgrade() -> None:
    if not _has_table("data_pipelines"):
        return
    columns = [
        ("environment", sa.Column("environment", sa.String(32), nullable=False, server_default="prod")),
        ("priority", sa.Column("priority", sa.String(16), nullable=False, server_default="medium")),
        ("sla_minutes", sa.Column("sla_minutes", sa.Integer(), nullable=False, server_default="120")),
        ("retry_count", sa.Column("retry_count", sa.Integer(), nullable=False, server_default="2")),
        ("timeout_minutes", sa.Column("timeout_minutes", sa.Integer(), nullable=False, server_default="60")),
        ("alert_policy_json", sa.Column("alert_policy_json", sa.JSON(), nullable=True)),
    ]
    for column_name, column in columns:
        if not _has_column("data_pipelines", column_name):
            op.add_column("data_pipelines", column)


def downgrade() -> None:
    for column_name in [
        "alert_policy_json",
        "timeout_minutes",
        "retry_count",
        "sla_minutes",
        "priority",
        "environment",
    ]:
        if _has_column("data_pipelines", column_name):
            op.drop_column("data_pipelines", column_name)
