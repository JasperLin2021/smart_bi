"""add dataset semantic model

Revision ID: 20260507_0015
Revises: 20260507_0014
Create Date: 2026-05-07
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260507_0015"
down_revision: Union[str, None] = "20260507_0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def _has_column(table_name: str, column_name: str) -> bool:
    if not _has_table(table_name):
        return False
    return any(column["name"] == column_name for column in sa.inspect(op.get_bind()).get_columns(table_name))


def upgrade() -> None:
    if _has_table("datasets") and not _has_column("datasets", "semantic_model_json"):
        op.add_column("datasets", sa.Column("semantic_model_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    if _has_column("datasets", "semantic_model_json"):
        op.drop_column("datasets", "semantic_model_json")
