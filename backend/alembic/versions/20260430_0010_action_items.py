"""add action items

Revision ID: 20260430_0010
Revises: 20260430_0009
Create Date: 2026-04-30
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260430_0010"
down_revision: Union[str, None] = "20260430_0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def _has_index(table_name: str, index_name: str) -> bool:
    if not _has_table(table_name):
        return False
    return any(index["name"] == index_name for index in sa.inspect(op.get_bind()).get_indexes(table_name))


def _create_index_if_missing(table_name: str, index_name: str, columns: list[str]) -> None:
    if _has_table(table_name) and not _has_index(table_name, index_name):
        op.create_index(index_name, table_name, columns, unique=False)


def upgrade() -> None:
    if not _has_table("action_items"):
        op.create_table(
            "action_items",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(length=160), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("source_type", sa.String(length=32), server_default="manual", nullable=False),
            sa.Column("source_id", sa.String(length=128), nullable=True),
            sa.Column("source_payload", sa.JSON(), nullable=True),
            sa.Column("linked_metric_id", sa.Integer(), nullable=True),
            sa.Column("linked_dataset_id", sa.Integer(), nullable=True),
            sa.Column("linked_dashboard_id", sa.Integer(), nullable=True),
            sa.Column("owner_id", sa.Integer(), nullable=True),
            sa.Column("priority", sa.String(length=16), server_default="medium", nullable=False),
            sa.Column("due_date", sa.Date(), nullable=True),
            sa.Column("status", sa.String(length=32), server_default="open", nullable=False),
            sa.Column("outcome", sa.Text(), nullable=True),
            sa.Column("org_id", sa.Integer(), nullable=True),
            sa.Column("created_by", sa.Integer(), nullable=True),
            sa.Column("closed_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
    for column in (
        "id",
        "title",
        "source_type",
        "source_id",
        "linked_metric_id",
        "linked_dataset_id",
        "linked_dashboard_id",
        "owner_id",
        "priority",
        "due_date",
        "status",
        "org_id",
        "created_by",
    ):
        _create_index_if_missing("action_items", op.f(f"ix_action_items_{column}"), [column])


def downgrade() -> None:
    if _has_table("action_items"):
        op.drop_table("action_items")
