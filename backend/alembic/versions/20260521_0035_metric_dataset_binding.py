"""add metric dataset binding

Revision ID: 20260521_0035
Revises: 20260514_0034, 20260520_0016
Create Date: 2026-05-21
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260521_0035"
down_revision: Union[str, tuple[str, str], None] = ("20260514_0034", "20260520_0016")
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
    if not _has_table("metrics"):
        return

    if not _has_column("metrics", "dataset_id"):
        op.add_column("metrics", sa.Column("dataset_id", sa.Integer(), nullable=True))

    if not _has_index("metrics", "ix_metrics_dataset_id"):
        op.create_index("ix_metrics_dataset_id", "metrics", ["dataset_id"], unique=False)

    if _has_table("datasets") and _has_column("metrics", "datasource_id") and _has_column("datasets", "datasource_id"):
        op.execute(
            """
            UPDATE metrics
            SET dataset_id = (
                SELECT MIN(datasets.id)
                FROM datasets
                WHERE datasets.datasource_id = metrics.datasource_id
            )
            WHERE dataset_id IS NULL
              AND datasource_id IS NOT NULL
              AND EXISTS (
                  SELECT 1
                  FROM datasets
                  WHERE datasets.datasource_id = metrics.datasource_id
              )
            """
        )


def downgrade() -> None:
    if _has_index("metrics", "ix_metrics_dataset_id"):
        op.drop_index("ix_metrics_dataset_id", table_name="metrics")
    if _has_column("metrics", "dataset_id"):
        op.drop_column("metrics", "dataset_id")
