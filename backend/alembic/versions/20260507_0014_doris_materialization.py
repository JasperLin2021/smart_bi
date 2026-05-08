"""add Doris dataset materialization fields

Revision ID: 20260507_0014
Revises: 20260506_0013
Create Date: 2026-05-07
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260507_0014"
down_revision: Union[str, None] = "20260506_0013"
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


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    if _has_table(table_name) and not _has_column(table_name, column.name):
        op.add_column(table_name, column)


def _create_index_if_missing(table_name: str, index_name: str, columns: list[str]) -> None:
    if _has_table(table_name) and not _has_index(table_name, index_name):
        op.create_index(index_name, table_name, columns, unique=False)


def upgrade() -> None:
    _add_column_if_missing("datasets", sa.Column("materialization_status", sa.String(length=32), nullable=True))
    _add_column_if_missing("datasets", sa.Column("materialization_mode", sa.String(length=32), nullable=True))
    _add_column_if_missing("datasets", sa.Column("materialized_table_name", sa.String(length=128), nullable=True))
    _add_column_if_missing("datasets", sa.Column("materialized_at", sa.DateTime(), nullable=True))
    _add_column_if_missing("datasets", sa.Column("incremental_key", sa.String(length=128), nullable=True))
    _add_column_if_missing("datasets", sa.Column("incremental_watermark", sa.String(length=256), nullable=True))
    _add_column_if_missing("datasets", sa.Column("materialization_message", sa.Text(), nullable=True))
    _create_index_if_missing("datasets", op.f("ix_datasets_materialization_status"), ["materialization_status"])
    _create_index_if_missing("datasets", op.f("ix_datasets_materialized_table_name"), ["materialized_table_name"])


def downgrade() -> None:
    for index_name in (op.f("ix_datasets_materialized_table_name"), op.f("ix_datasets_materialization_status")):
        if _has_index("datasets", index_name):
            op.drop_index(index_name, table_name="datasets")
    for column in (
        "materialization_message",
        "incremental_watermark",
        "incremental_key",
        "materialized_at",
        "materialized_table_name",
        "materialization_mode",
        "materialization_status",
    ):
        if _has_column("datasets", column):
            op.drop_column("datasets", column)
