"""add metric trust center fields

Revision ID: 20260430_0009
Revises: 20260430_0008
Create Date: 2026-04-30
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260430_0009"
down_revision: Union[str, None] = "20260430_0008"
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
    _add_column_if_missing(
        "metrics",
        sa.Column("certification_status", sa.String(length=32), server_default="draft", nullable=False),
    )
    _add_column_if_missing("metrics", sa.Column("certified_by", sa.String(length=128), nullable=True))
    _add_column_if_missing("metrics", sa.Column("certified_at", sa.DateTime(), nullable=True))
    _add_column_if_missing(
        "metrics",
        sa.Column("caliber_version", sa.String(length=64), server_default="v1", nullable=False),
    )
    _add_column_if_missing("metrics", sa.Column("data_updated_at", sa.DateTime(), nullable=True))
    _add_column_if_missing(
        "metrics",
        sa.Column("quality_status", sa.String(length=32), server_default="unknown", nullable=False),
    )
    _add_column_if_missing("metrics", sa.Column("quality_message", sa.Text(), nullable=True))
    _add_column_if_missing("metrics", sa.Column("lineage_json", sa.JSON(), nullable=True))
    _create_index_if_missing("metrics", op.f("ix_metrics_certification_status"), ["certification_status"])
    _create_index_if_missing("metrics", op.f("ix_metrics_quality_status"), ["quality_status"])


def downgrade() -> None:
    for index_name in (op.f("ix_metrics_quality_status"), op.f("ix_metrics_certification_status")):
        if _has_index("metrics", index_name):
            op.drop_index(index_name, table_name="metrics")
    for column in (
        "lineage_json",
        "quality_message",
        "quality_status",
        "data_updated_at",
        "caliber_version",
        "certified_at",
        "certified_by",
        "certification_status",
    ):
        if _has_column("metrics", column):
            op.drop_column("metrics", column)
