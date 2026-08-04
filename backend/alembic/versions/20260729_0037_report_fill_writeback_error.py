"""add report fill record writeback error

Revision ID: 20260729_0037
Revises: 20260729_0036
Create Date: 2026-07-29
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260729_0037"
down_revision: Union[str, tuple[str, str], None] = "20260729_0036"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def _has_column(table_name: str, column_name: str) -> bool:
    if not _has_table(table_name):
        return False
    return any(column["name"] == column_name for column in sa.inspect(op.get_bind()).get_columns(table_name))


def upgrade() -> None:
    if not _has_table("report_fill_records"):
        return
    if not _has_column("report_fill_records", "writeback_error"):
        op.add_column("report_fill_records", sa.Column("writeback_error", sa.Text(), nullable=True))


def downgrade() -> None:
    if _has_column("report_fill_records", "writeback_error"):
        op.drop_column("report_fill_records", "writeback_error")
