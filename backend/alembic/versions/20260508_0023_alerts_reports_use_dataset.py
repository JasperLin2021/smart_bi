"""alerts and scheduled_reports bind to dataset instead of datasource

Revision ID: 20260508_0023
Revises: 20260508_0022
Create Date: 2026-05-08
"""

from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "20260508_0023"
down_revision: Union[str, None] = "20260508_0022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def _has_column(table_name: str, column_name: str) -> bool:
    if not _has_table(table_name):
        return False
    return any(column["name"] == column_name for column in sa.inspect(op.get_bind()).get_columns(table_name))


def _has_index(table_name: str, index_name: str) -> bool:
    if not _has_table(table_name):
        return False
    return any(index["name"] == index_name for index in sa.inspect(op.get_bind()).get_indexes(table_name))


def upgrade() -> None:
    if _has_table("alerts") and not _has_column("alerts", "dataset_id"):
        op.add_column("alerts", sa.Column("dataset_id", sa.Integer(), nullable=True))
    if _has_table("alerts") and not _has_index("alerts", "ix_alerts_dataset_id"):
        op.create_index("ix_alerts_dataset_id", "alerts", ["dataset_id"])

    if _has_table("scheduled_reports") and not _has_column("scheduled_reports", "dataset_id"):
        op.add_column("scheduled_reports", sa.Column("dataset_id", sa.Integer(), nullable=True))
    if _has_table("scheduled_reports") and not _has_index("scheduled_reports", "ix_scheduled_reports_dataset_id"):
        op.create_index("ix_scheduled_reports_dataset_id", "scheduled_reports", ["dataset_id"])


def downgrade() -> None:
    if _has_index("scheduled_reports", "ix_scheduled_reports_dataset_id"):
        op.drop_index("ix_scheduled_reports_dataset_id", table_name="scheduled_reports")
    if _has_column("scheduled_reports", "dataset_id"):
        op.drop_column("scheduled_reports", "dataset_id")

    if _has_index("alerts", "ix_alerts_dataset_id"):
        op.drop_index("ix_alerts_dataset_id", table_name="alerts")
    if _has_column("alerts", "dataset_id"):
        op.drop_column("alerts", "dataset_id")
