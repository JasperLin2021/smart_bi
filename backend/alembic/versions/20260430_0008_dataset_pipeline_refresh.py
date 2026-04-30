"""add dataset pipeline refresh logs

Revision ID: 20260430_0008
Revises: 20260429_0007
Create Date: 2026-04-30
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260430_0008"
down_revision: Union[str, None] = "20260429_0007"
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


def _has_index(table_name: str, index_name: str) -> bool:
    if not _has_table(table_name):
        return False
    return any(index["name"] == index_name for index in sa.inspect(op.get_bind()).get_indexes(table_name))


def _create_index_if_missing(table_name: str, index_name: str, columns: list[str]) -> None:
    if _has_table(table_name) and not _has_index(table_name, index_name):
        op.create_index(index_name, table_name, columns, unique=False)


def upgrade() -> None:
    _add_column_if_missing("datasets", sa.Column("pipeline_json", sa.JSON(), nullable=True))
    _add_column_if_missing("datasets", sa.Column("last_refresh_status", sa.String(length=32), nullable=True))
    _add_column_if_missing("datasets", sa.Column("last_refresh_at", sa.DateTime(), nullable=True))
    _add_column_if_missing(
        "datasets",
        sa.Column("last_refresh_row_count", sa.Integer(), server_default="0", nullable=False),
    )

    if not _has_table("dataset_refresh_logs"):
        op.create_table(
            "dataset_refresh_logs",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("dataset_id", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("row_count", sa.Integer(), server_default="0", nullable=False),
            sa.Column("message", sa.Text(), nullable=True),
            sa.Column("org_id", sa.Integer(), nullable=True),
            sa.Column("triggered_by_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
            sa.ForeignKeyConstraint(["dataset_id"], ["datasets.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_if_missing("dataset_refresh_logs", op.f("ix_dataset_refresh_logs_id"), ["id"])
    _create_index_if_missing("dataset_refresh_logs", op.f("ix_dataset_refresh_logs_dataset_id"), ["dataset_id"])
    _create_index_if_missing("dataset_refresh_logs", op.f("ix_dataset_refresh_logs_status"), ["status"])
    _create_index_if_missing("dataset_refresh_logs", op.f("ix_dataset_refresh_logs_org_id"), ["org_id"])
    _create_index_if_missing(
        "dataset_refresh_logs",
        op.f("ix_dataset_refresh_logs_triggered_by_id"),
        ["triggered_by_id"],
    )


def downgrade() -> None:
    if _has_table("dataset_refresh_logs"):
        op.drop_table("dataset_refresh_logs")
    for column in ("last_refresh_row_count", "last_refresh_at", "last_refresh_status", "pipeline_json"):
        if _has_column("datasets", column):
            op.drop_column("datasets", column)
