"""add p1 p2 foundation

Revision ID: 20260429_0007
Revises: 20260429_0006
Create Date: 2026-04-30
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260429_0007"
down_revision: Union[str, None] = "20260429_0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def _has_column(table_name: str, column_name: str) -> bool:
    if not _has_table(table_name):
        return False
    return any(column["name"] == column_name for column in sa.inspect(op.get_bind()).get_columns(table_name))


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    if not _has_column(table_name, column.name):
        op.add_column(table_name, column)


def _has_index(table_name: str, index_name: str) -> bool:
    if not _has_table(table_name):
        return False
    return any(index["name"] == index_name for index in sa.inspect(op.get_bind()).get_indexes(table_name))


def _create_dataset_table() -> None:
    if _has_table("datasets"):
        return
    op.create_table(
        "datasets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("datasource_id", sa.Integer(), nullable=False),
        sa.Column("fields_json", sa.JSON(), nullable=True),
        sa.Column("filters_json", sa.JSON(), nullable=True),
        sa.Column("derived_columns_json", sa.JSON(), nullable=True),
        sa.Column("joins_json", sa.JSON(), nullable=True),
        sa.Column("aggregations_json", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="draft", nullable=False),
        sa.Column("visibility", sa.String(length=32), server_default="private", nullable=False),
        sa.Column("org_id", sa.Integer(), nullable=True),
        sa.Column("owner_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("id", "name", "datasource_id", "status", "org_id", "owner_id"):
        op.create_index(op.f(f"ix_datasets_{column}"), "datasets", [column], unique=False)


def _create_big_screen_table() -> None:
    if _has_table("big_screens"):
        return
    op.create_table(
        "big_screens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("canvas_json", sa.JSON(), nullable=True),
        sa.Column("data_bindings_json", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="draft", nullable=False),
        sa.Column("visibility", sa.String(length=32), server_default="private", nullable=False),
        sa.Column("org_id", sa.Integer(), nullable=True),
        sa.Column("owner_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("id", "title", "status", "org_id", "owner_id"):
        op.create_index(op.f(f"ix_big_screens_{column}"), "big_screens", [column], unique=False)


def upgrade() -> None:
    _add_column_if_missing("dashboards", sa.Column("is_public", sa.Integer(), server_default="0", nullable=False))
    _add_column_if_missing("dashboards", sa.Column("share_token", sa.String(length=64), nullable=True))
    _add_column_if_missing("dashboards", sa.Column("shared_user_ids", sa.JSON(), nullable=True))
    _add_column_if_missing("dashboards", sa.Column("version", sa.Integer(), server_default="1", nullable=False))
    if _has_table("dashboards") and not _has_index("dashboards", op.f("ix_dashboards_share_token")):
        op.create_index(op.f("ix_dashboards_share_token"), "dashboards", ["share_token"], unique=True)
    _create_dataset_table()
    _create_big_screen_table()


def downgrade() -> None:
    if _has_table("big_screens"):
        op.drop_table("big_screens")
    if _has_table("datasets"):
        op.drop_table("datasets")
    if _has_table("dashboards"):
        try:
            op.drop_index(op.f("ix_dashboards_share_token"), table_name="dashboards")
        except Exception:
            pass
        for column in ("version", "shared_user_ids", "share_token", "is_public"):
            if _has_column("dashboards", column):
                op.drop_column("dashboards", column)
