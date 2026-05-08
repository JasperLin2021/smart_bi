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


def upgrade() -> None:
    op.add_column("alerts", sa.Column("dataset_id", sa.Integer(), nullable=True))
    op.create_index("ix_alerts_dataset_id", "alerts", ["dataset_id"])

    op.add_column("scheduled_reports", sa.Column("dataset_id", sa.Integer(), nullable=True))
    op.create_index("ix_scheduled_reports_dataset_id", "scheduled_reports", ["dataset_id"])


def downgrade() -> None:
    op.drop_index("ix_scheduled_reports_dataset_id", table_name="scheduled_reports")
    op.drop_column("scheduled_reports", "dataset_id")

    op.drop_index("ix_alerts_dataset_id", table_name="alerts")
    op.drop_column("alerts", "dataset_id")
